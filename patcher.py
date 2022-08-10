import requests
import plistlib
import remotezip
import subprocess
import shutil
import os
import asyncio
import utils

def async_run(func):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(func)

class InitError(Exception):
	pass

class ProgressError(Exception):
	pass

def isIdentifierExists(identifier):
	return False



def getFirmwareUrl(identifier, version):
	r = requests.get(f"https://api.ipsw.me/v2.1/{identifier}/{version}/url")
	try: # this version has multiple BuildIDs
		return r.json(), True # isJson(True)
	except:
		return r.text, False # isJson(False

def getDevicesJson():
		return requests.get("https://api.ipsw.me/v4/devices").json()


class ramdiskMaker:
	def __init__(self, identifier, version, buildid=None, callback=None):
		self.callback = callback if callback else print
		async_run(self.callback(f"init: {identifier}, {version}, {buildid}, {callback}"))
		self.identifier = identifier
		if "iPhone" not in self.identifier and "iPad" not in self.identifier and "iPod" not in self.identifier:
			raise InitError("Product is not supported")
		self.version = version
		self.buildid = buildid
		self.verint = int(version[:2])
		if not 11 <= self.verint <= 14:
			raise InitError("Version is not supported")
		self.tempdir = f"{version}_{identifier}"
		devices_json = getDevicesJson()
		for device in devices_json:
			if device["identifier"] == self.identifier:
				self.boardconfig = device["boards"][0]["boardconfig"].lower()
				break
		if os.path.exists(self.tempdir):
			shutil.rmtree(self.tempdir)
		os.makedirs(self.tempdir)

	def isOutExists(self):
		try:
			return utils.read_key(f"{self.tempdir}_{self.buildid}")
		except:
			return None

	def extractFile(self, remotePath, outDir):
		z = remotezip.RemoteZip(self.url)
		return z.extract(remotePath, outDir)

	def getFirmwareUrl(self):
		if not self.buildid:
			async_run(self.callback("Requesting firmware URL with identifier"))
			r = requests.get(f"https://api.ipsw.me/v2.1/{self.identifier}/{self.version}/url")
		else:
			async_run(self.callback("Requesting firmware URL with BuildID"))
			r = requests.get(f"https://api.ipsw.me/v2.1/{self.identifier}/{self.version}/url")
		async_run(self.callback(r.text))
		try: # this version has multiple BuildIDs
			return r.json()[0], True # isJson(True)
		except:
			return r.text, False # isJson(False

	def setFirmwareUrl(self, url, buildid=None):
		if buildid:
			self.buildid = buildid
			async_run(self.callback(f"ProductBuildVersion: {self.buildid}"))
		self.url = url
		async_run(self.callback(f"Firmware URL set to {self.url}"))

	def loadManifest(self):
		async_run(self.callback("Extracting BuildManifest"))
		buildManifestPath = self.extractFile("BuildManifest.plist", self.tempdir)
		with open(buildManifestPath, "rb") as f:
			_plist = plistlib.load(f)
		if not self.buildid:
			async_run(self.callback(f"ProductBuildVersion: {self.buildid}"))
			self.buildid = _plist["ProductBuildVersion"]
		return _plist

	def extractRamdisk(self, _plist):
		async_run(self.callback("Extracting ramdisk"))
		# get BuildIdentity
		restoreramdiskpath = None
		for buildidentity in _plist["BuildIdentities"]:
			if buildidentity["Info"]["DeviceClass"] == self.boardconfig:
				restoreramdiskpath = buildidentity["Manifest"]["RestoreRamDisk"]["Info"]["Path"]
				break
		async_run(self.callback(restoreramdiskpath))
		if not restoreramdiskpath:
			raise ProgressError("Could not get ramdisk path")
		# extract ramdisk
		return self.extractFile(restoreramdiskpath, self.tempdir)

	def patchRamdisk(self, path):
		async_run(self.callback("Starting patch"))
		ret = subprocess.run(["img4","-i", path, "-o", f"{self.tempdir}/ramdisk.dmg"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if ret.returncode != 0:
			raise ProgressError(f"Unpacking ramdisk failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
		if not os.path.exists(f"{self.tempdir}/mountpoint"):
			os.makedirs(f"{self.tempdir}/mountpoint")
		async_run(self.callback("Mounting ramdisk"))
		ret = subprocess.run(["hdiutil","attach",f"{self.tempdir}/ramdisk.dmg","-mountpoint",f"{self.tempdir}/mountpoint"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if ret.returncode != 0:
			raise ProgressError(f"Mounting ramdisk failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
		
		# patch ASR
		async_run(self.callback("Patching ASR"))
		shutil.move(f"{self.tempdir}/mountpoint/usr/sbin/asr", f"{self.tempdir}/asr.extracted")
		ret = subprocess.run(["asr64_patcher", f"{self.tempdir}/asr.extracted", f"{self.tempdir}/asr.patched"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if ret.returncode != 0:
			subprocess.run(["hdiutil","detach",f"{self.tempdir}/mountpoint"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			raise ProgressError(f"Patching ASR failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
		ret = subprocess.run(f"ldid -e {self.tempdir}/asr.extracted > {self.tempdir}/asr.xml", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if ret.returncode != 0:
			subprocess.run(["hdiutil","detach",f"{self.tempdir}/mountpoint"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			raise ProgressError(f"Extracting ASR entitlements failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
		ret = subprocess.run(["ldid",f"-S{self.tempdir}/asr.xml",f"{self.tempdir}/asr.patched"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if ret.returncode != 0:
			subprocess.run(["hdiutil","detach",f"{self.tempdir}/mountpoint"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			raise ProgressError(f"Adding back entitlements to patched ASR failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
		os.chmod(f"{self.tempdir}/asr.patched", 0o755)
		shutil.move(f"{self.tempdir}/asr.patched", f"{self.tempdir}/mountpoint/usr/sbin/asr")

		# patch restored_external
		if self.verint >= 14:
			async_run(self.callback("Patching restored_external"))
			shutil.move(f"{self.tempdir}/mountpoint/usr/local/bin/restored_external", f"{self.tempdir}/restored_external.extracted")
			ret = subprocess.run(["restored_external64_patcher", f"{self.tempdir}/restored_external.extracted", f"{self.tempdir}/restored_external.patched"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			if ret.returncode != 0:
				subprocess.run(["hdiutil","detach",f"{self.tempdir}/mountpoint"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				raise ProgressError(f"Patching restored_external failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
			ret = subprocess.run(f"ldid -e {self.tempdir}/restored_external.extracted > {self.tempdir}/restored_external.xml", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			if ret.returncode != 0:
				subprocess.run(["hdiutil","detach",f"{self.tempdir}/mountpoint"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				raise ProgressError(f"Extracting restored_external entitlements failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
			ret = subprocess.run(["ldid" ,f"-S{self.tempdir}/restored_external.xml", f"{self.tempdir}/restored_external.patched"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			if ret.returncode != 0:
				subprocess.run(["hdiutil","detach",f"{self.tempdir}/mountpoint"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				raise ProgressError(f"Adding back entitlements to patched restored_external failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
			os.chmod(f"{self.tempdir}/restored_external.patched", 0o755)
			shutil.move(f"{self.tempdir}/restored_external.patched", f"{self.tempdir}/mountpoint/usr/local/bin/restored_external")
		subprocess.run(["hdiutil","detach",f"{self.tempdir}/mountpoint"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		if not os.path.exists(f"out/{self.tempdir}"):
			os.makedirs(f"out/{self.tempdir}")
		async_run(self.callback("Repacking ramdisk"))
		ret = subprocess.run(["img4","-i",f"{self.tempdir}/ramdisk.dmg","-o",f"ramdisk_{self.tempdir}_{self.buildid}.im4p","-A","-T","rdsk"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if ret.returncode != 0:
			raise ProgressError(f"Repacking ramdisk failed with return code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
		async_run(self.callback("patch done"))
		return f"ramdisk_{self.tempdir}_{self.buildid}.im4p"

	def uploadRamdisk(self, path):
		async_run(self.callback("Uploading ramdisk"))
		ret = subprocess.run(["gdrive","upload",path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if ret.returncode != 0:
			raise ProgressError(f"Failed to upload ramdisk\nreturn code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
		# parse output to get fileid
		line = ret.stdout.decode("utf-8").splitlines()[1]
		# line looks like this: Uploaded FILEID at /s, total
		fileid = line.split(" ")[1]
		async_run(self.callback(fileid))
		ret = subprocess.run(["gdrive","share",fileid], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if ret.returncode != 0:
			raise ProgressError(f"Failed to publish (share) ramdisk\nreturn code: {ret.returncode}\nstdout={ret.stdout}\nstderr={ret.stderr}")
		utils.write_key(f"{self.tempdir}_{self.buildid}", f"https://drive.google.com/file/d/{fileid}/view?usp=sharing")
		return f"https://drive.google.com/file/d/{fileid}/view?usp=sharing"

	def cleanUp(self):
		async_run(self.callback("Cleaning up"))
		if os.path.isfile(f"ramdisk_{self.tempdir}_{self.buildid}.im4p"):
			os.remove(f"ramdisk_{self.tempdir}_{self.buildid}.im4p")
		if os.path.exists(self.tempdir):
			shutil.rmtree(self.tempdir)

