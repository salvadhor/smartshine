#!/usr/bin/env python
# -*- coding: utf-8 -*-


# License : GPLv3 : http://gplv3.fsf.org/

try:
    import os, sys
    import os.path
    import subprocess
    import shutil
    import time
    import threading
    import re
    import ConfigParser
    import operator
    import cairo
    import pyexiv2
    from gi.repository import Gdk, Gtk, GObject, GdkPixbuf
except:
    print('An error occured. Python or one of its sub modules is absent...\nIt would be wise to check your python installation.')
    sys.exit(1)    

try:
    import Image    
    from PIL.ExifTags import TAGS
except:
    print('Python Imaging Library is missing.')

APP = 'SmartShine Photo'
__VERSION__='0.36'
__LICENSE__='GPL'
__COPYRIGHT__='Dariusz Duma'
__WEBSITE__='http://launchpad.net/smartshine'

if os.path.exists('/usr/share/smartshine/ui/smartshine_g3.ui') \
    and os.path.exists('/usr/share/smartshine/pixmaps/smartshine.png'):
    DIR = '/usr/share/smartshine/locale/'
    IMG = '/usr/share/smartshine/pixmaps/'
    UI = '/usr/share/smartshine/ui/'

elif os.path.exists(sys.path[0] + "/ui/smartshine_g3.ui"):
    DIR = sys.path[0] + '/locale/'
    IMG = sys.path[0] + '/images/'
    UI = sys.path[0] + '/ui/'
else:
    print ("That's me, your SmartShine. Make your mind - local or system wide install?")
    sys.exit(1)
    
import locale
import gettext

locale.setlocale(locale.LC_ALL, '')
gettext.bindtextdomain(APP, DIR)
gettext.textdomain(APP)
gettext.install(APP)
_ = gettext.gettext
    
GObject.threads_init()

####################################################
######## Class: system    ##########################
####################################################

class Donnees:
    """System"""
    def __init__(self):
        self.install_dossier=sys.path[0]                                                #On recupere le dossier d'install
        
        self.home_dossier = (os.getenv('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')) + '/smartshine'
        self.enfuse_dossier = self.home_dossier
        self.previs_dossier = self.enfuse_dossier + "/preview"
        if not os.path.isdir(self.enfuse_dossier):
            os.makedirs(self.enfuse_dossier)
        if not os.path.isdir(self.previs_dossier):
            os.makedirs(self.previs_dossier)
            
        self.default_folder=os.path.expanduser('~/')
        self.default_file=""
        
    def check_install(self, name):
        a=False
        for dir in os.environ['PATH'].split(":"):
            prog = os.path.join(dir, name)
            if os.path.exists(prog): 
                a=True
        return a

##############################################################
###########Class: interface     ##############################
##############################################################

class Interface:
    """Interface"""

    def __init__(self):
        
        if not donnees.check_install("aaphoto"):
            self.messageinthebottle(_("Can't find aaPhoto.\nPlease check aaPhoto is installed.\nStopping..."))
            sys.exit()

        self.options={_("Flip horizontally"): "--flipx", \
                    _("Flip vertically"): "--flipy", \
                    _("Rotate 90"): "--rotate90", \
                    _("Rotate 180"): "--rotate180", \
                    _("Rotate 270"): "--rotate270", \
                    "Reset": ""}
                    
        self.builder = Gtk.Builder()
        self.builder.add_from_file(UI + "smartshine_g3.ui") 
        self.window = self.builder.get_object("window1")
        self.window.set_title('SmartShine Photo')
        self.window.set_default_icon_from_file(IMG + 'smartshine.png') 
        self.listeimages = self.builder.get_object("listeimages") 
        self.combobox = self.builder.get_object("as_format1")
        self.store = Gtk.ListStore(GObject.TYPE_STRING)
        self.combobox.set_model(self.store)
        self.combobox.append_text("jpg")
        self.combobox.append_text("jp2")
        self.combobox.append_text("png")
        self.combobox.append_text("bmp")
        self.combobox.set_active(0)
        self.image_width = self.builder.get_object("image_width")       # image width - default
        self.image_width.set_range(1,9999)
        self.image_width_px = self.builder.get_object("image_width_px")
        self.image_width_percent = self.builder.get_object("image_width_percent")
        self.image_width_px.set_active(1)
        self.save_exif = self.builder.get_object("save_exif")           # save exif button - default
        self.save_exif.set_active(1)
        self.jpgquality = self.builder.get_object("jpgquality")         # jpg quality - default
        self.jpgquality.set_value(92)
        self.saveto = self.builder.get_object("filechooserbutton2")     # default folder to save
        self.spinner = self.builder.get_object("spinner1")
        
        dic = { "on_window1_destroy" : self.exit_app,
                "on_Quit_clicked" : self.exit_app,
                "on_Info_clicked" : self.about,
                "on_add_photos_clicked" : self.add_images,
                "on_remove_clicked" : self.rm_from_list,
                "on_image_width_value_changed" : self.spinchanges,
                "on_image_width_px_toggled" : self.ptoggled,
                "on_flipx_clicked" : self.fliprotate,
                "on_flipy_clicked" : self.fliprotate,
                "on_rotate90_clicked" : self.fliprotate,
                "on_rotate180_clicked" : self.fliprotate,
                "on_rotate270_clicked" : self.fliprotate,
                "on_reset_clicked" : self.fliprotate,
                "on_save_all_clicked" : self.save_to_starter,
                "on_listeimages_cursor_changed" : self.get_params
                }                 
        
        self.builder.connect_signals(dic)
        self.inittreeview()
        self.fileslist=''
        self.window.show_all()  

    def exit_app(self, action):
        self.stop_now = True
        self.closing_app = True
        self.cleanup()
        sys.exit(0)
               
    def get_active(self, widget):
        self.selection = self.listeimages.get_selection()
        self.selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        (tree_model, tree_iter) = self.selection.get_selected_rows()
        return (tree_model, tree_iter)
        
    def spinchanges(self, widget):
        tree_model, tree_iter = self.get_active(widget)
        for i in tree_iter:
            oneiter = tree_model.get_iter(i)
            self.selected_user = tree_model.get_value(oneiter, 0)
            pb = GdkPixbuf.Pixbuf.new_from_file(tree_model.get_value(oneiter, 0))
            im = self.pixbuf2Image(pb)
            if im.size[0] < im.size[1]:
                if self.image_width.get_value_as_int() < im.size[1]:            
                    tree_model.set_value(oneiter, 5, self.image_width.get_value_as_int())
                    self.update_info(tree_model, oneiter, 0)        
            else:
                if self.image_width.get_value_as_int() < im.size[0]:            
                    tree_model.set_value(oneiter, 5, self.image_width.get_value_as_int())
                    self.update_info(tree_model, oneiter, 0)        
            
    def get_params(self, widget):
        (tree_model, tree_iter) = self.get_active(widget)
        for i in tree_iter:
            oneiter = tree_model.get_iter(i)
            self.selected_user = tree_model.get_value(oneiter, 0)
            if tree_model.get_value(oneiter, 5):
                self.image_width.set_value(float(tree_model.get_value(oneiter, 5)))
            else:
                pb = GdkPixbuf.Pixbuf.new_from_file(tree_model.get_value(oneiter, 0))
                im = self.pixbuf2Image(pb)
                self.image_width.set_value(str(im.size[0]))
    
    def ptoggled(self, widget): #TODO - recalculate spinbutton value
        if widget.get_active():
            self.messageinthebottle("click!")    
    
    def fliprotate(self, widget):                   # 0 - flip, 1 - rotate
        label = widget.get_label()

        tree_model, tree_iter = self.get_active(widget)
        for i in tree_iter:
            oneiter = tree_model.get_iter(i)
            self.photo_thumb = tree_model.get_value(oneiter, 7)
            path, file = os.path.split(self.photo_thumb)
            self.rm_if_exist(self.photo_thumb, path)
            if label == _("Flip horizontally") or label == _("Flip vertically"):
                copyb = tree_model.get_value(oneiter, 6)[1]
                if tree_model.get_value(oneiter,6)[0] != self.options[label]:
                    self.default_settings = [self.options[label], copyb, "-a", "-o"]
                    tree_model.set_value(oneiter, 6, [self.options[label], copyb])
                else:
                    self.default_settings = ["", copyb, "-a", "-o"]
                    tree_model.set_value(oneiter, 6, ["", copyb])
            elif label == "Reset":
                self.default_settings = ["-a", "-o"]
                tree_model.set_value(oneiter, 6, ["",""])
            else:
                copyb = tree_model.get_value(oneiter, 6)[0]
                if tree_model.get_value(oneiter,6)[1] != self.options[label]:
                    self.default_settings = [copyb, self.options[label], "-a", "-o"]
                    tree_model.set_value(oneiter, 6, [copyb, self.options[label]])
                else:
                    self.default_settings = [copyb, "", "-a", "-o"]
                    tree_model.set_value(oneiter, 6, [copyb, ""])
            self.default_settings = filter(None, self.default_settings) # fastest
            self.photo_thumb_new = self.make_thumb_prev(self.photo_thumb, self.default_settings)
            tree_model.set_value(oneiter, 2, GdkPixbuf.Pixbuf.new_from_file(path + "/" + self.fileaa))
            self.update_info(tree_model, oneiter, label)

    def rm_if_exist(self, photo, where):
        path, photo = os.path.split(photo)
        fileaanew, fileaaext = os.path.splitext(photo)
        self.fileaa = fileaanew + "_new" + ".jpg"
        if os.path.isfile(where + "/" + self.fileaa):
            os.remove(where + "/" + self.fileaa)
                
    def update_info(self, tree_model, oneiter, helper):
        info=""
        im = self.pixbuf2Image(GdkPixbuf.Pixbuf.new_from_file(tree_model.get_value(oneiter, 0)))
        flip = tree_model.get_value(oneiter, 6)[0]
        rotate = tree_model.get_value(oneiter, 6)[1]
        inv_options = dict((self.options[k], k) for k in self.options)
        if tree_model.get_value(oneiter, 6): # check rotate
            if flip:
                info = "<span size=\"large\"><b>" +_("Flip:\t\t\t") + "</b></span><i>" + str(inv_options[flip]) + "</i>\n"     
            else:
                info = ""
            if rotate:
                info += "<span size=\"large\"><b>" +_("Rotate:\t\t\t") + "</b></span><i>" + str(inv_options[rotate]) + "</i>\n"     
            else:
                info += ""
        if im.size[0] < im.size[1]:
            if int(tree_model.get_value(oneiter, 5)) < im.size[1]: # check resolution
                info += "<span size=\"large\"><b>" + _("Resize to:\t\t") + "</b></span><i>" + str(tree_model.get_value(oneiter, 5)) + "px</i>\n"
        else:
            if int(tree_model.get_value(oneiter, 5)) < im.size[0]: # check resolution
                info += "<span size=\"large\"><b>" + _("Resize to:\t\t") + "</b></span><i>" + str(tree_model.get_value(oneiter, 5)) + "px</i>\n"
        info += "\n"
        tree_model.set_value(oneiter, 3, info + tree_model.get_value(oneiter,8))

    def about(self, widget):
        self.win=about_app()
        
    def about2(self, widget):
        self.win=about_app2()

    def cleanup(self):
        for self.files in os.walk(donnees.previs_dossier):
            for self.filename in self.files[2]:
                os.remove(donnees.previs_dossier + "/" + self.filename)
   
    def inittreeview(self):
        """initialize photo preview tree"""
        self.liststoreimport = Gtk.ListStore(str, GdkPixbuf.Pixbuf, GdkPixbuf.Pixbuf, str, object, int, object, str, str)
        #                                   photo_name, thumb, thumb, info, settings, width, rorate/flip, thumbnail, orginal_info)
        self.listeimages.set_model(self.liststoreimport)                      
        
        self.imagebefore = Gtk.TreeViewColumn(_("Before"))                    
        self.listeimages.append_column(self.imagebefore)                      
        self.cellrender = Gtk.CellRendererPixbuf()                            
        #self.imagebefore.set_sizing(320)
        self.imagebefore.pack_start(self.cellrender, True)                    
        self.imagebefore.add_attribute(self.cellrender, 'pixbuf', 1)
        self.cellrender.set_property('visible', 1)
        
        self.imageafter = Gtk.TreeViewColumn(_("After"))                       
        self.listeimages.append_column(self.imageafter)                     
        self.cellrender2 = Gtk.CellRendererPixbuf()                         
        #self.imageafter.set_sizing(320)
        self.imageafter.pack_start(self.cellrender2, True)          
        self.imageafter.add_attribute(self.cellrender2, 'pixbuf', 2)
        self.cellrender2.set_property('visible', 1)
        
        self.imageact = Gtk.TreeViewColumn(_('Actions & Info'))      
        self.listeimages.append_column(self.imageact)                
        self.cell = Gtk.CellRendererText()                           
        self.imageact.pack_start(self.cell, True)                    
        self.imageact.add_attribute(self.cell, 'markup', 3)           
        
        self.listeimages.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self.listeimages.set_rules_hint(True)
    
    def add_images(self, widget):
        FenOuv=open_files(self.liststoreimport,1)
        self.liststoreimport=FenOuv.get_model()
        
    def messageinthebottle(self, message):
        self.messaga=Gtk.MessageDialog(parent=None, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, message_format=(message))
        if self.messaga.run() == Gtk.ResponseType.OK:
            self.messaga.destroy()

    def open_images(self, widget):
        FenOuv=open_files(self.liststoreimport,0)
        self.liststoreimport=FenOuv.get_model()
        
        
    def rm_from_list(self, widget):
        self.treeselectionsuppr=self.listeimages.get_selection()                
        self.treeselectionsuppr.set_mode(Gtk.SelectionMode.MULTIPLE)                #get seletecd rows from list
        (model, pathlist) = self.treeselectionsuppr.get_selected_rows()
        for i in sorted(pathlist, reverse=True ):
            treeiter = model.get_iter(i)
            self.liststoreimport.remove(treeiter) 
    
    def pixbuf2Image(self, pb):
        width,height = pb.get_width(),pb.get_height()
        return Image.fromstring("RGB",(width,height),pb.get_pixels() )
    
    def get_exif(self, fichier):
        tags2=''
        tags={}
        exifinfo=None
        try:
            im = pyexiv2.ImageMetadata(fichier)
            im.read()
            tags_keys = im.exif_keys
            if tags_keys != '':
                if 'Exif.Image.Model' in tags_keys: 
                    tags2=(_("<i>Model:</i>\t\t\t") + str(im['Exif.Image.Model'].value) + "\n")
                if 'Exif.Image.DateTimeOriginal' in tags_keys: 
                    tags2+=(_("<i>Date:</i>\t\t\t") + str(im['Exif.Image.DateTimeOriginal'].value) + "\n")
                if 'Exif.Photo.FocalLength' in tags_keys:
                    tags2+=(_("<i>Focal length:</i>\t\t") + str(int(im['Exif.Photo.FocalLength'].value)) + "mm \n")
                if 'Exif.Photo.FNumber' in tags_keys:
                    tags2+=(_("<i>Aperture:</i>\t\t\tF/") + str(im['Exif.Photo.FNumber'].value) + "\n")
                if 'Exif.Photo.ExposureTime' in tags_keys:
                    tags2+=(_("<i>Exposure Time:</i>\t\t") + str(im['Exif.Photo.ExposureTime'].value) + " s. \n")
        except IOError:
            print "failed to identify", file
        return tags2
        
    def put_files_to_the_list(self, photos):
        self.photos=photos
        self.tags2=''
        self.badfiles=[]
        self.default_settings=["-a", "-o"]
        for photo in self.photos:
            if re.search('\\.jpg$|\\.jpeg$|\\.png$|\\.bmp$|\\.jp2$|\\.ppm$', photo, flags=re.IGNORECASE):
                self.photo_thumb=self.make_thumb(photo,(int(512), int(512)))
                pb = GdkPixbuf.Pixbuf.new_from_file(photo)
                im = self.pixbuf2Image(pb)
                self.size = im.size
                if self.size[0] > self.size[1]:
                    self.width = self.size[0]
                else:
                    self.width = self.size[1]
                self.tags2 = self.get_exif(photo)
                self.photo_thumb_new = self.make_thumb_prev(self.photo_thumb, self.default_settings) # !!!! Check, if exist
                if not self.tags2:
                    self.tags2=''
                self.tooltip=("<span size=\"large\"><b>"+_("Auto-corrected:")+"</b></span> \n" \
                "<i>"+_("Contrast")+"\n"+_("Color balance")+"\n"+_("Saturation")+"\n"+_("Gamma levels")+"</i>\n\n" \
                "<span size=\"large\"><b>Info:</b></span>\n" \
                + "<i>"+_("Filename:")+"</i>\t\t\t" + os.path.basename(photo) + "\n<i>"+_("Resolution:")+"</i>\t\t" + str(str(self.size[0]) + "x" + str(self.size[1])) + " px\n" + self.tags2 +"")
                self.liststoreimport.append([photo, \
                    GdkPixbuf.Pixbuf.new_from_file(self.photo_thumb), \
                    GdkPixbuf.Pixbuf.new_from_file(self.photo_thumb_new), \
                    self.tooltip, \
                    self.default_settings, \
                    self.width, \
                    ["",""], \
                    self.photo_thumb, \
                    self.tooltip])
            else:
                self.badfiles.append(photo)
        if len(self.badfiles)>0:
            messaga=_("Only JPEG and TIFF files are allowed.\n\nCannot open:\n")
            for itz in self.badfiles:
                messaga+=itz + "\n"
            Gui.messageinthebottle(messaga)
        return 

    def make_thumb_prev(self, photo_thumb, default_settings):
        self.command=["aaphoto"] + self.default_settings + [donnees.previs_dossier + "/", self.photo_thumb]
        preview_process=subprocess.Popen(self.command, stdout=subprocess.PIPE)
        preview_process.wait()
        return os.path.splitext(self.photo_thumb)[0] + "_new" + os.path.splitext(self.photo_thumb)[1]
    
    def make_thumb(self,file,width):
        outfile=donnees.previs_dossier + '/' + os.path.splitext(os.path.split(file)[1])[0] + ".jpg"
        self.rm_if_exist(file, donnees.previs_dossier)          # rm if thumb exist
        try:
            im = GdkPixbuf.Pixbuf.new_from_file_at_size(file, width[0], width[1])
            im.savev(outfile, "jpeg", [], [])
        except IOError:
            print _("Generating %s thumbnail failed.") % chemin
        return outfile

    def save_to_starter(self, widget):
        thread = OutputThread(Gui.work_finished_cb)
        thread.daemon = True
        thread.start()

    def save_to(self):
        saveto = self.saveto.get_current_folder()
        rotate=""
        resize=""
        for item in self.liststoreimport:
            settings = []
            rotate=""
            resize=""
            self.rm_if_exist(item[0], saveto)                   #remove existed _new files
            pb = GdkPixbuf.Pixbuf.new_from_file(item[0])
            im = self.pixbuf2Image(pb)
            rotate = item[6]                        # rotate
            rotate = filter(None, rotate)
            if im.size[0] <= im.size[1] and int(item[5]) < im.size[1]:             # resize
                    resize = "-r" + str(item[5])
            elif im.size[0] >= im.size[1] and int(item[5]) < im.size[0]:
                    resize = "-r"+ str(item[5])
            else:
                resize = ''
            quality = "-q" + str(self.jpgquality.get_value_as_int())   # quality
            filetype = "--" + self.combobox.get_active_text()  # filetype
            if rotate:
                settings += rotate
            if resize != '':
                settings.append(resize)
            if not self.save_exif.get_active():
                settings += ["--noexif"]
            settings += [quality,  filetype,  "-a", "-o", saveto, str(item[0])]
            self.command = ["aaphoto"] + settings
            preview_process = subprocess.Popen(self.command, stdout=subprocess.PIPE)
            preview_process.wait()
        return
        
            
    def work_finished_cb(self):

        return

###########################################################    
####  Class: Threads                                   ####
###########################################################

class WorkerThread(threading.Thread):
    def __init__(self, callback, fichiers):
        threading.Thread.__init__(self)
        self.fichiers=fichiers
        self.callback = callback
        self.about = about_app2() # start spinner
    
    def run(self):
        Gui.put_files_to_the_list(self.fichiers)
        GObject.idle_add(self.callback)
        time.sleep(1)
        self.about.close_about()    # stop spinner

class OutputThread(threading.Thread):
    def __init__(self, callback):
        threading.Thread.__init__(self)
        self.callback = callback
        self.about = about_app2()   # start spinner
            
    def run(self):
        Gui.save_to()
        GObject.idle_add(self.callback)
        time.sleep(1)
        self.about.close_about()   # stop spinner         
        
###########################################################    
####  Class: Files                                     ####
###########################################################

class open_files:
    """Add photos to the list"""
    def __init__(self,model,add_or_open):
        """choose files"""
        self.filtre=Gtk.FileFilter()
        self.filtre.add_mime_type("image/jpeg")
        self.filtre.add_mime_type("image/x-portable-pixmap")
        self.filtre.add_mime_type("image/png")
        self.filtre.add_mime_type("image/bmp")
        self.filtre.add_mime_type("image/jp2")

        self.liststoreimport=model #set model for the list
        if add_or_open:
            self.fenetre_ouvrir = Gtk.FileChooserDialog(_("Add images..."), 
                                                        None, 
                                                        Gtk.FileChooserAction.OPEN,
                                                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
            self.fenetre_ouvrir.set_select_multiple(True)
            self.fenetre_ouvrir.set_current_folder(donnees.default_folder)
            self.fenetre_ouvrir.set_filter(self.filtre)
            self.fenetre_ouvrir.use_preview = True
            self.previewidget = Gtk.Image()
            self.fenetre_ouvrir.set_preview_widget(self.previewidget)
            self.fenetre_ouvrir.connect("update-preview", self.update_thumb_preview, self.previewidget)
        else:
            self.fenetre_ouvrir = Gtk.FileChooserDialog(_("Open images..."), 
                                                       None, 
                                                       Gtk.FileChooserAction.OPEN,
                                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
            self.fenetre_ouvrir.set_select_multiple(True) 
            self.fenetre_ouvrir.set_current_folder(donnees.default_folder)
            self.fenetre_ouvrir.set_filter(self.filtre)
            self.fenetre_ouvrir.use_preview = True
            self.previewidget = Gtk.Image()
            self.fenetre_ouvrir.set_preview_widget(self.previewidget)
            self.fenetre_ouvrir.connect("update-preview", self.update_thumb_preview, self.previewidget)
            self.liststoreimport.clear()     
        
        if ( self.fenetre_ouvrir.run() == Gtk.ResponseType.OK):
            self.fichiers = self.fenetre_ouvrir.get_filenames()
            self.tags2=''
            self.badfiles=[]
            Gui.fileslist = self.fichiers
            thread = WorkerThread(Gui.work_finished_cb, self.fichiers)
            thread.daemon = True
            thread.start()

        donnees.default_folder=self.fenetre_ouvrir.get_current_folder()
        self.fenetre_ouvrir.hide() # UGLY Gtk bug - opening more files drives to slowdown (cause of data caching in recently-used.xbel)
        
    def update_thumb_preview(self, file_chooser, preview):
        if not self.fenetre_ouvrir.use_preview:
            return
        filename = file_chooser.get_preview_filename()
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename, 320, 320)
            self.previewidget.set_from_pixbuf(pixbuf)
            self.have_preview = True
        except:
            self.have_preview = False
        self.fenetre_ouvrir.set_preview_widget_active(self.have_preview)
        return
                 
    def get_model(self):
        """ Retourne la liststore """
        if self.liststoreimport:
            return self.liststoreimport
        else:
            return None        
            
########################################    
#### About                          ####
########################################  

class about_app:
    def __init__(self):
        self.aboutdialog = Gtk.AboutDialog()
        self.aboutdialog.set_program_name("SmartShine Photo")
        self.aboutdialog.set_transient_for(Gui.window)
        self.aboutdialog.set_modal(True)
        self.aboutdialog.set_version(__VERSION__)
        self.aboutdialog.set_comments('Automation for the photographers - aaphoto in action.\n\nSmartShine Photo (c) 2012 Dariusz Duma\n<dhor@toxic.net.pl>\naaPhoto (c) 2012 András Horváth\n<mail@log69.com>\n')
        self.aboutdialog.set_website(__WEBSITE__)
        self.aboutdialog.connect("response", self.close_about)
        self.aboutdialog.show()
        
    def close_about(self, widget, event):
        self.aboutdialog.destroy()
        
class about_app2:
    def __init__(self):
        self.aboutdialog = Gtk.Dialog()
        
        self.aboutdialog.set_default_size(320, 320)
        self.spinner = Gtk.Spinner()
        self.label = Gtk.Label(_("Working..."))
        box = self.aboutdialog.get_content_area()
        box.add(self.spinner)
        box.add(self.label)
        box.set_child_packing(self.spinner, 1, 1, 0, 0)
        self.aboutdialog.set_transient_for(Gui.window)
        self.aboutdialog.set_modal(True)
        self.spinner.start()
        self.aboutdialog.show_all()
        
    def close_about(self):
        self.aboutdialog.destroy()
        
###########################################################    
####  Init                                             ####
###########################################################            
                        
if __name__ == "__main__":
    
    donnees=Donnees()                                                          #Variables 
    Gui = Interface()                                                          #Interface

    Gtk.main()     
