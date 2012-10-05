import os
import subprocess
from subprocess import Popen
import time
import shutil
import gettext
import stat
import commands
from configobj import ConfigObj

gettext.install("debi-installer", "/usr/share/locale")
	   
class SystemUser:
    ''' Represents the main user '''
   
    def __init__(self, username=None, realname=None, password=None):
	''' create new SystemUser '''
	self.username = username
	self.realname = realname
	self.password = password	

class HostMachine:
	''' Used to probe information about the host '''
	
	def is_laptop(self):
		''' Returns True/False as to whether the host is a laptop '''
		ret = False
		try:
			p = Popen("laptop-detect", shell=True)
			p.wait() # we want the return code
			retcode = p.returncode
			if(retcode == 0):
				# its a laptop
				ret = True
		except:
			pass # doesn't matter, laptop-detect doesnt exist on the host
		return ret
		
	def get_model(self):
		''' return the model of the pooter '''
		ret = None
		try:
			model = commands.getoutput("dmidecode --string system-product-name")
			ret = model.rstrip("\r\n").lstrip()
		except:
			pass # doesn't matter.
		return ret
		
	def get_manufacturer(self):
		''' return the system manufacturer '''
		ret = None
		try:
			manu = commands.getoutput("dmidecode --string system-manufacturer")
			ret = manu.rstrip("\r\n ").lstrip()
		except:
			pass # doesn't matter
		return ret
			
class InstallerEngine:
    ''' This is central to the live installer '''
   
    def __init__(self):
	# set up stuffhs
	self.conf_file = '/etc/live-installer/install.conf'
	configuration = ConfigObj(self.conf_file)
	distribution = configuration['distribution']
	install = configuration['install']
	self.distribution_name = distribution['DISTRIBUTION_NAME']
	self.distribution_version = distribution['DISTRIBUTION_VERSION']

	self.user = None
	self.live_user = install['LIVE_USER_NAME']
	self.set_install_media(media=install['LIVE_MEDIA_SOURCE'], type=install['LIVE_MEDIA_TYPE'])
	
	self.grub_device = None
	
    def set_main_user(self, user):
	''' Set the main user to be used by the installer '''
	if(user is not None):
		self.user = user
       
    def get_main_user(self):
	''' Return the main user '''
	return self.user
           
    def format_device(self, device, filesystem):
	''' Format the given device to the specified filesystem '''
	if filesystem == "swap":
		cmd = "mkswap %s" % device
	else:
		if (filesystem == "jfs"):
			cmd = "mkfs.%s -q %s" % (filesystem, device)
		elif (filesystem == "xfs"):
			cmd = "mkfs.%s -f %s" % (filesystem, device)
		else:
			cmd = "mkfs.%s %s" % (filesystem, device)
			
	p = Popen(cmd, shell=True)
	p.wait() # this blocks
	return p.returncode
       
    def set_install_media(self, media=None, type=None):
	''' Sets the location of our install source '''
	self.media = media
	self.media_type = type

    def set_keyboard_options(self, layout=None, model=None):
	''' Set the required keyboard layout and model with console-setup '''
	self.keyboard_layout = layout
	self.keyboard_model = model

    def set_hostname(self, hostname):
	''' Set the hostname on the target machine '''
	self.hostname = hostname

    def set_install_bootloader(self, device=None):
	''' The device to install grub to '''
	self.grub_device = device
		
    def add_to_blacklist(self, blacklistee):
	''' This will add a directory or file to the blacklist, so that '''
	''' it is not copied onto the new filesystem '''
	try:
		self.blacklist.index(blacklistee)
		self.blacklist.append(blacklistee)
	except:
	# We haven't got this item yet
		pass

    def set_progress_hook(self, progresshook):
	''' Set a callback to be called on progress updates '''
	''' i.e. def my_callback(progress_type, message, current_progress, total) '''
	''' Where progress_type is any off PROGRESS_START, PROGRESS_UPDATE, PROGRESS_COMPLETE, PROGRESS_ERROR '''
	self.update_progress = progresshook

    def get_distribution_name(self):
	return self.distribution_name
       
    def get_distribution_version(self):
	return self.distribution_version
       
    def get_locale(self):
	''' Return the locale we're setting '''
	return self.locale
   
    def set_locale(self, newlocale):
	''' Set the locale '''
	self.locale = newlocale
    def do_run_in_chroot(self, command):
        os.system("chroot /target/ /bin/sh -c \"%s\"" % command)
        
    def install(self):
	''' Install this baby to disk '''
	# mount the media location.
	try:
		if(not os.path.exists("/target")):
			os.mkdir("/target")
			os.mkdir("/target/home")
			os.mkdir("/target/tmp")
			os.mkdir("/target/boot")
			os.mkdir("/target/srv")
		if(not os.path.exists("/source")):
			os.mkdir("/source")
		# find the squashfs..
		root = self.media
		root_type = self.media_type
		if(not os.path.exists(root)):
			print _("Base filesystem does not exist! Bailing")
			sys.exit(1) # change to report
		root_device = None
		tmp_device = None
		boot_device = None
		home_device = None
		srv_device = None
		# format partitions as appropriate
		for item in self.fstab.get_entries():
			if(item.mountpoint == "/"):
				root_device = item
				item.format = True
			elif(item.mountpoint == "/tmp"):
				tmp_device = item
				item.format = True
			elif(item.mountpoint == "/boot"):
				boot_device = item
				item.format = True
			elif(item.mountpoint == "/home"):
				home_device = item
			elif(item.mountpoint == "/srv"):
				srv_device = item
				item.format = True
			if(item.format):
				# well now, we gets to nuke stuff.
				# report it. should grab the total count of filesystems to be formatted ..
				self.update_progress(total=4, current=1, pulse=True, message=_("Formatting %s as %s..." % (item.device, item.filesystem)))
				self.format_device(item.device, item.filesystem)
		# mount filesystem
		self.update_progress(total=4, current=2, message=_("Mounting %s on %s") % (root, "/source/"))
		self.do_mount(root, "/source/", root_type, options="loop")
		self.update_progress(total=4, current=3, message=_("Mounting %s on %s") % (root_device.device, "/target/"))
		self.do_mount(root_device.device, "/target", root_device.filesystem, None)
		if tmp_device != None:
			self.do_mount(tmp_device.device, "/target/tmp", tmp_device.filesystem, None)
		if boot_device != None:
			self.do_mount(boot_device.device, "/target/boot", boot_device.filesystem, None)
		if home_device != None:
			self.do_mount(home_device.device, "/target/home", home_device.filesystem, None)
		if srv_device != None:
			self.do_mount(srv_device.device, "/target/srv", srv_device.filesystem, None)
		# walk root filesystem. we're too lazy though :P
		SOURCE = "/source/"
		DEST = "/target/"
		directory_times = []
		our_total = 0
		our_current = -1
		os.chdir(SOURCE)
		# index the files
		for top,dirs,files in os.walk(SOURCE, topdown=False):
			our_total += len(dirs) + len(files)
			self.update_progress(pulse=True, message=_("Indexing files to be copied.."))
		our_total += 1 # safenessness
		for top,dirs,files in os.walk(SOURCE):
			# Sanity check. Python is a bit schitzo
			dirpath = top
			if(dirpath.startswith(SOURCE)):
				dirpath = dirpath[len(SOURCE):]
			for name in dirs + files:
				# following is hacked/copied from Ubiquity
				rpath = os.path.join(dirpath, name)
				sourcepath = os.path.join(SOURCE, rpath)
				targetpath = os.path.join(DEST, rpath)
				st = os.lstat(sourcepath)
				mode = stat.S_IMODE(st.st_mode)

				# now show the world what we're doing
				our_current += 1
				self.update_progress(total=our_total, current=our_current, message=_("Copying %s" % rpath))

				if stat.S_ISLNK(st.st_mode):
					if os.path.lexists(targetpath):
						os.unlink(targetpath)
					linkto = os.readlink(sourcepath)
					os.symlink(linkto, targetpath)
				elif stat.S_ISDIR(st.st_mode):
					if not os.path.isdir(targetpath):
						os.mkdir(targetpath, mode)
				elif stat.S_ISCHR(st.st_mode):
					os.mknod(targetpath, stat.S_IFCHR | mode, st.st_rdev)
				elif stat.S_ISBLK(st.st_mode):
					os.mknod(targetpath, stat.S_IFBLK | mode, st.st_rdev)
				elif stat.S_ISFIFO(st.st_mode):
					os.mknod(targetpath, stat.S_IFIFO | mode)
				elif stat.S_ISSOCK(st.st_mode):
					os.mknod(targetpath, stat.S_IFSOCK | mode)
				elif stat.S_ISREG(st.st_mode):
					# we don't do blacklisting yet..
					try:
						os.unlink(targetpath)
					except:
						pass
					self.copy_file(sourcepath, targetpath)
				os.lchown(targetpath, st.st_uid, st.st_gid)
				if not stat.S_ISLNK(st.st_mode):
					os.chmod(targetpath, mode)
				if stat.S_ISDIR(st.st_mode):
					directory_times.append((targetpath, st.st_atime, st.st_mtime))
				# os.utime() sets timestamp of target, not link
				elif not stat.S_ISLNK(st.st_mode):
					os.utime(targetpath, (st.st_atime, st.st_mtime))
			# Apply timestamps to all directories now that the items within them
			# have been copied.
		for dirtime in directory_times:
			(directory, atime, mtime) = dirtime
			try:
				self.update_progress(pulse=True, message=_("Restoring meta-information on %s" % directory))
				os.utime(directory, (atime, mtime))
			except OSError:
				pass
		# Steps:
		our_total = 8
		our_current = 0
		# chroot
		self.update_progress(total=our_total, current=our_current, message=_("Entering new system.."))
		os.system("mkfifo /target/tmp/INSTALL_PIPE")
		os.system("mount --bind /dev/ /target/dev/")
		os.system("mount --bind /dev/shm /target/dev/shm")
		os.system("mount --bind /dev/pts /target/dev/pts")
		os.system("mount --bind /sys/ /target/sys/")
		os.system("mount --bind /proc/ /target/proc/")
		os.system("cp -f /etc/resolv.conf /target/etc/resolv.conf")
		
		
			
			
			
		# remove live user
		live_user = self.live_user
		our_current += 1
		self.sub_update_progress(total=our_total, current=our_current, message=_("Removing live configuration (user)"))
		self.do_run_in_chroot("deluser %s" % live_user)
		# can happen
		if(os.path.exists("/target/home/%s" % live_user)):
			os.system("rm -rf /target/home/%s" % live_user)
		# remove live-initramfs (or w/e)
		our_current += 1
		self.sub_update_progress(total=our_total, current=our_current, message=_("Removing live configuration (packages)"))
		self.do_run_in_chroot("apt-get remove --purge --yes --force-yes live-initramfs debi-installer")
			
		# add new user
		our_current += 1
		self.sub_update_progress(total=our_total, current=our_current, message=_("Adding user to system"))
		os.mkdir("/target/home")
		user = self.get_main_user()
		self.do_run_in_chroot("useradd -s %s -c \'%s\' -G sudo -m %s" % ("/bin/bash", user.realname, user.username))			
		newusers = open("/target/tmp/newusers.conf", "w")
		newusers.write("%s:%s\n" % (user.username, user.password))
		newusers.write("root:%s\n" % user.password)
		newusers.close()
		self.do_run_in_chroot("cat /tmp/newusers.conf | chpasswd")
		self.do_run_in_chroot("rm -rf /tmp/newusers.conf")
		
		# write the /etc/fstab
		our_current += 1
		self.sub_update_progress(total=our_total, current=our_current, message=_("Writing filesystem mount information"))
		# make sure fstab has default /proc and /sys entries
		if(not os.path.exists("/etc/fstab")):
			os.system("echo \"#### Static Filesystem Table File\" > /target/etc/fstab")
		fstabber = open("/target/etc/fstab", "a")
		fstabber.write("proc\t/proc\tproc\tnodev,noexec,nosuid\t0\t0\n")
		for item in self.fstab.get_entries():
			if(item.options is None):
				item.options = "rw,errors=remount-ro"
			if(item.filesystem == "swap"):
				# special case..
				fstabber.write("%s\tswap\tswap\tsw\t0\t0\n" % item.device)
			else:
				fstabber.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (item.device, item.mountpoint, item.filesystem, item.options, "0", "0"))
		fstabber.close()
		# write host+hostname infos
		our_current += 1
		self.sub_update_progress(total=our_total, current=our_current, message=_("Setting hostname"))
		hostnamefh = open("/target/etc/hostname", "w")
		hostnamefh.write("%s\n" % self.hostname)
		hostnamefh.close()
		hostsfh = open("/target/etc/hosts", "w")
		hostsfh.write("127.0.0.1\tlocalhost\n")
		hostsfh.write("127.0.1.1\t%s\n" % self.hostname)
		hostsfh.write("# The following lines are desirable for IPv6 capable hosts\n")
		hostsfh.write("::1     localhost ip6-localhost ip6-loopback\n")
		hostsfh.write("fe00::0 ip6-localnet\n")
		hostsfh.write("ff00::0 ip6-mcastprefix\n")
		hostsfh.write("ff02::1 ip6-allnodes\n")
		hostsfh.write("ff02::2 ip6-allrouters\n")
		hostsfh.write("ff02::3 ip6-allhosts\n")
		hostsfh.close()
		
		# restore slim
		os.system("sed -i -e 's/auto_login/#auto_login/g' /target/etc/slim.conf")
		os.system("sed -i -e 's/default_user/#default_user/g' /target/etc/slim.conf")
		

		
		# set the locale
		our_current += 1
		self.sub_update_progress(total=our_total, current=our_current, message=_("Setting locale"))
		os.system("echo \"%s.UTF-8 UTF-8\" >> /target/etc/locale.gen" % self.locale)
            	self.do_run_in_chroot("locale-gen")
            	os.system("echo \"\" > /target/etc/default/locale")
            	self.do_run_in_chroot("update-locale LANG=\"%s.UTF-8\"" % self.locale)
            	self.do_run_in_chroot("update-locale LANG=%s.UTF-8" % self.locale)


			# set the keyboard options..
		our_current += 1
		self.sub_update_progress(total=our_total, current=our_current, message=_("Setting keyboard options"))
		consolefh = open("/etc/default/console-setup", "r")
		newconsolefh = open("/etc/default/console-setup.new", "w")
		for line in consolefh:
			line = line.rstrip("\r\n")
			if(line.startswith("XKBMODEL=")):
				newconsolefh.write("XKBMODEL=\"%s\"\n" % self.keyboard_model)
			elif(line.startswith("XKBLAYOUT=")):
				newconsolefh.write("XKBLAYOUT=\"%s\"\n" % self.keyboard_layout)
			else:
				newconsolefh.write("%s\n" % line)
		consolefh.close()
		newconsolefh.close()
		os.system("rm /etc/default/console-setup")
		os.system("mv /etc/default/console-setup.new /etc/default/console-setup")


		
		# write MBR (grub)
		our_current += 1
			
		self.do_run_in_chroot("grub-install --force %s" % self.grub_device)
		self.do_run_in_chroot("grub-mkconfig -o /boot/grub/grub.cfg")
		# now unmount it
		os.system("umount --force /target/dev/shm")
		os.system("umount --force /target/dev/pts")
		os.system("umount --force /target/dev/")
		os.system("umount --force /target/sys/")
		os.system("umount --force /target/proc/")
		self.do_unmount("/target")
		self.do_unmount("/source")



		self.update_progress(done=True, message=_("Installation finished"))
	except Exception,detail:
		print detail

    def sub_update_progress(self, total=None,current=None,fail=False,done=False,message=None):
	''' Only called from the chroot '''
	if(fail or done):
		os.system("echo \"DONE\" >> /tmp/INSTALL_PIPE")
	else:
		os.system("echo \"%s\" >> /tmp/INSTALL_PIPE" % message)
			
    def do_mount(self, device, dest, type, options=None):
	''' Mount a filesystem '''
	p = None
	if(options is not None):
		p = Popen("mount -o %s -t %s %s %s" % (options, type, device, dest),shell=True)
	else:
		p = Popen("mount -t %s %s %s" % (type, device, dest),shell=True)
	p.wait()
	return p.returncode
       
    def do_unmount(self, mountpoint):
	''' Unmount a filesystem '''
	p = Popen("umount %s" % mountpoint, shell=True)
	p.wait()
	return p.returncode
       
    def copy_file(self, source, dest):
	# TODO: Add md5 checks. BADLY needed..
	BUF_SIZE = 16 * 1024
	input = open(source, "rb")
	dst = open(dest, "wb")
	while(True):
		read = input.read(BUF_SIZE)
		if not read:
			break
		dst.write(read)
	input.close()
	dst.close()
	   
class fstab(object):
    ''' This represents the filesystem table (/etc/fstab) '''
    def __init__(self):
	self.mapping = dict()
       
    def add_mount(self, device=None, mountpoint=None, filesystem=None, options=None,format=False):
	if(not self.mapping.has_key(device)):
		self.mapping[device] = fstab_entry(device, mountpoint, filesystem, options)
		self.mapping[device].format = format
   
    def remove_mount(self, device):
	if(self.mapping.has_key(device)):
		del self.mapping[device]

    def get_entries(self):
	''' Return our list '''
	return self.mapping.values()

    def has_device(self, device):
	return self.mapping.has_key(device)
		
    def has_mount(self, mountpoint):
	for item in self.get_entries():
		if(item.mountpoint == mountpoint):
			return True
	return False
		
class fstab_entry(object):
    ''' Represents an entry in fstab '''
   
    def __init__(self, device, mountpoint, filesystem, options):
	''' Creates a new fstab entry '''
	self.device = device
	self.mountpoint = mountpoint
	self.filesystem = filesystem
	self.options = options
	self.format = False
