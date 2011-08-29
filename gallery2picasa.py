#!/usr/bin/python

from modules import db
from modules import flags
from modules import items
from modules import utils

from datetime import datetime
import Image
import gdata.photos
import gdata.photos.service
import sys
import time
import os

FLAGS = flags.FLAGS
FLAGS.AddFlag('b', 'dbuser', 'The username to use for the database')
FLAGS.AddFlag('a', 'dbpass', 'The password to use for the database')
FLAGS.AddFlag('d', 'database', 'The database to use', 'gallery2')
FLAGS.AddFlag('h', 'hostname', 'The database hostname', 'localhost')
FLAGS.AddFlag('t', 'table_prefix', 'The table prefix to use', 'g2_')
FLAGS.AddFlag('f', 'field_prefix', 'The field prefix to use', 'g_')
FLAGS.AddFlag('u', 'username', 'The Google username to use')
FLAGS.AddFlag('p', 'password', 'The Google password to use')
FLAGS.AddFlag('g', 'gallery_prefix', 'Gallery album directory',
    '/var/local/g2data/albums')
FLAGS.AddFlag('z', 'album', 'Album to upload, or "all"', 'all')
FLAGS.AddFlag('l', 'list', '"yes" to not upload, just list albums', False)

def main(argv):
    appname = argv[0]

    try:
        argv = FLAGS.Parse(argv[1:])
    except flags.FlagParseError, e:
        utils.Usage(appname, e.usage(), e.message())
        sys.exit(1)

    print 'Connecting to %s on %s...' % (FLAGS.database, FLAGS.hostname)
    gdb = db.Database(FLAGS.dbuser, FLAGS.dbpass, FLAGS.database,
            FLAGS.hostname, FLAGS.table_prefix, FLAGS.field_prefix)

    print 'Connecting to PicasaWeb using %s...' % (FLAGS.username)
    pws = gdata.photos.service.PhotosService()
    pws.ClientLogin(FLAGS.username, FLAGS.password)

    try:
      print 'Getting a list of Gallery albums...',
      albums = []
      album_ids = gdb.ItemIdsForTable(items.AlbumItem.TABLE_NAME)
      print 'found %s, loading...' % (len(album_ids))
      for id in album_ids:
          albums.append(items.AlbumItem(gdb, id))

      print 'Loading photos in albums:                   ',
      photos_by_album = {}
      photo_ids = gdb.ItemIdsForTable(items.PhotoItem.TABLE_NAME)
      for id in photo_ids:
          photo = items.PhotoItem(gdb, id)
          if photo.parent_id() not in photos_by_album:
              photos_by_album[photo.parent_id()] = []
              print '\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08%6d of %6d' % (
                      reduce(lambda sum, x: len(x) + sum,
                          photos_by_album.values(), 0),
                      len(photo_ids)),
              sys.stdout.flush()
          photos_by_album[photo.parent_id()].append(photo)

      print '\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08done! (%d)             \n' % len(photo_ids)

      for album in albums:
          if album.id() not in photos_by_album:
              continue

          if FLAGS.list != False:
              print 'ALBUM [%s] [%s] (%d photos)' % (
                      album.full_path(albums), album.title(),
                      len(photos_by_album[album.id()]))
              continue

          if FLAGS.album != "all" and FLAGS.album != album.title():
              continue

          yesno = raw_input("Upload '%s: %s' [yN]?: " % (
              album.full_path(albums), album.title())).lower()
          if not yesno.startswith('y'):
              continue

          # find a reasonable date for album
          album_path = FLAGS.gallery_prefix + '/' + album.full_path(albums)
          files = os.listdir(album_path)
          dt = datetime.now()
          if len(files) > 0:
              i = Image.open(album_path + '/' + files[0])
              exifdate = i._getexif().get(306)
              if exifdate != None:
                  dt = datetime.strptime(exifdate, "%Y:%m:%d %H:%M:%S")
          timestamp = str(int(time.mktime(dt.timetuple()) * 1000))
          print 'CREATING ALBUM [%s] [%s] [%s (%s)]' % (
                  album.title(), album.summary(), dt.ctime(), timestamp)
          a = pws.InsertAlbum(
                  title=album.title(),
                  summary=album.summary(),
                  access="private",
                  timestamp=timestamp)

          for photo in photos_by_album[album.id()]:
              title = photo.title()
          if (photo.path_component().startswith(photo.title())):
              title = ''
          non_empty = filter(lambda x: len(x) > 0,
                  (title, photo.summary(), photo.description()))
          comment = "; ".join(non_empty)
          print '\tCREATING PHOTO [%s] [%s] [%s]' % (
                  photo.path_component(), comment, photo.keywords())

          keywords = ', '.join(photo.keywords().split())
          filename = '%s/%s' % (album_path, photo.path_component())
          pws.InsertPhotoSimple(a.GetFeedLink().href,
                  photo.path_component(), comment, filename,
                  'image/jpeg', keywords)

    finally:
        gdb.close()

if __name__ == '__main__':
    main(sys.argv)
