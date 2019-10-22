#!/usr/bin/env python
from yahoogroupsapi import YahooGroupsAPI
import json
import email
import urllib
import os
from os.path import basename
from xml.sax.saxutils import unescape
import argparse
import getpass
import sys
import traceback


def unescape_html(string):
    return unescape(string, {"&quot;": '"', "&apos;": "'", "&#39;": "'"})


def get_best_photoinfo(photoInfoArr):
    rs = {'tn': 0, 'sn': 1, 'hr': 2, 'or': 3}
    best = photoInfoArr[0]
    for info in photoInfoArr:
        if rs[info['photoType']] >= rs[best['photoType']]:
            best = info
    return best


def archive_email(out_dir, yga, reattach=True, save=True, skip_if_exists=True):
    msg_json = yga.messages()
    count = msg_json['totalRecords']

    msg_json = yga.messages(count=count)
    print "Group has %s messages, got %s" % (count, msg_json['numRecords'])

    for message in msg_json['messages']:
        message_id = message['messageId']
        fname = os.path.join(out_dir, "%s.eml" % (message_id))
        if skip_if_exists and os.path.exists(fname):
            print "* Found saved email %s. skipping. " % (fname)
            continue

        print "* Fetching raw message #%d of %d" % (message_id, count)
        raw_json = {}
        try:
            raw_json = yga.messages(message_id, 'raw')
        except Exception:
            print "* 500 ERROR Retrieving %s" % (message_id)
            with open(fname, 'w') as f:
                f.write(traceback.format_exc())
            continue
        mime = unescape_html(raw_json['rawEmail']).encode('latin_1', 'ignore')

        eml = email.message_from_string(mime)

        if (save or reattach) and message['hasAttachments']:
            atts = {}
            if 'attachments' not in message:
                print "** Yahoo says this message has attachments, but I can't find any!"
            else:
                for attach in message['attachments']:
                    print "** Fetching attachment '%s'" % (attach['filename'],)
                    if 'link' in attach:
                        atts[attach['filename']] = yga.get_file(attach['link'])
                    elif 'photoInfo' in attach:
                        photoinfo = get_best_photoinfo(attach['photoInfo'])
                        atts[attach['filename']] = yga.get_file(
                            photoinfo['displayURL'])

                    if save:
                        fname = os.path.join(out_dir, "%s-%s" % (message_id, basename(attach['filename'])))
                        if os.path.exists(fname) and skip_if_exists:
                            print "* skipping downloading of attachment %s as it already exists" % (fname)
                            continue
                        with open(fname, 'wb') as f:
                            f.write(atts[attach['filename']])

                if reattach:
                    for part in eml.walk():
                        fname = part.get_filename()
                        if fname and fname in atts:
                            part.set_payload(atts[fname])
                            email.encoders.encode_base64(part)
                            del atts[fname]

        fname = os.path.join(out_dir, "%s.eml" % (message_id))
        print([fname])
        with open(fname, 'w') as f:
            f.write(eml.as_string(unixfrom=False))
            # f.write("Hello")


def archive_files(out_dir, yga, subdir=None, skip_if_exists=True):
    if subdir:
        file_json = yga.files(sfpath=subdir)
    else:
        file_json = yga.files()

    fileinfo_out_file = os.path.join(out_dir, 'fileinfo.json')
    with open(fileinfo_out_file, 'w') as f:
        f.write(json.dumps(file_json['dirEntries'], indent=4))

    n = 0
    sz = len(file_json['dirEntries'])
    for path in file_json['dirEntries']:
        n += 1
        if path['type'] == 0:
            # Regular file
            name = unescape_html(path['fileName'])
            print "* Fetching file '%s' (%d/%d)" % (name, n, sz)
            out_filename = os.path.join(out_dir, basename(name))
            if os.path.exists(out_filename) and skip_if_exists:
                print "* Found %s. skipping download.." % (out_filename)
                continue
            with open(out_filename, 'wb') as f:
                yga.download_file(path['downloadURL'], f)

        elif path['type'] == 1:
            # Directory
            print "* Fetching directory '%s' (%d/%d)" % (path['fileName'], n, sz)
            with Mkchdir(basename(path['fileName']).replace('.', '')):
                pathURI = urllib.unquote(path['pathURI'])
                archive_files(out_dir, yga, subdir=pathURI, skip_if_exists=skip_if_exists)


def archive_photos(out_dir, yga, skip_if_exists=True):
    albums = yga.albums()
    n = 0

    for a in albums['albums']:
        n += 1
        name = unescape_html(a['albumName'])
        # Yahoo has an off-by-one error in the album count...
        print "* Fetching album '%s' (%d/%d)" % (name, n, albums['total'] - 1)

        with Mkchdir(basename(name).replace('.', '')):
            photos = yga.albums(a['albumId'])
            p = 0

            for photo in photos['photos']:
                p += 1
                pname = unescape_html(photo['photoName'])
                print "** Fetching photo '%s' (%d/%d)" % (pname, p, photos['total'])

                photoinfo = get_best_photoinfo(photo['photoInfo'])
                fname = os.path.join(out_dir, "%d-%s.jpg" % (photo['photoId'], basename(pname)))
                if os.path.exists(fname) and skip_if_exists:
                    print "* %s already exists. skipping img." % (fname)
                with open(fname, 'wb') as f:
                    yga.download_file(photoinfo['displayURL'], f)


def archive_db(out_dir, yga, group, skip_if_exists=True):
    json = yga.database()
    n = 0
    nts = len(json['tables'])
    for table in json['tables']:
        n += 1
        print "* Downloading database table '%s' (%d/%d)" % (table['name'], n, nts)

        name = os.path.join(out_dir, basename(table['name']) + '.csv')
        uri = "https://groups.yahoo.com/neo/groups/%s/database/%s/records/export?format=csv" % (
            group, table['tableId'])
        if os.path.exists(name):
            print("* DB %s exists. skipping." % (name))
            continue
        with open(name, 'w') as f:
            yga.download_file(uri, f)


class Mkchdir:
    d = ""

    def __init__(self, d):
        self.d = d

    def __enter__(self):
        try:
            os.mkdir(self.d)
        except OSError:
            pass
        os.chdir(self.d)

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir('..')


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument('--out_dir', type=str, default='data', help='output dir')
    p.add_argument('-u', '--username', type=str)
    p.add_argument('-p', '--password', type=str,
                   help='If no password supplied, will be requested on the console')
    p.add_argument('-ct', '--cookie_t', type=str)
    p.add_argument('-cy', '--cookie_y', type=str)
    p.add_argument('-c', '--resume', help='skip downloading existing files.', action="store_true")

    po = p.add_argument_group(title='What to archive',
                              description='By default, all the below.')
    po.add_argument('-e', '--email', action='store_true',
                    help='Only archive email and attachments')
    po.add_argument('-f', '--files', action='store_true',
                    help='Only archive files')
    po.add_argument('-i', '--photos', action='store_true',
                    help='Only archive photo galleries')
    po.add_argument('-d', '--database', action='store_true',
                    help='Only archive database')

    pe = p.add_argument_group(title='Email Options')
    pe.add_argument('-r', '--no-reattach', action='store_true',
                    help="Don't reattach attachment files to email")
    pe.add_argument('-s', '--no-save', action='store_true',
                    help="Don't save email attachments as individual files")

    p.add_argument('group', type=str)

    args = p.parse_args()
    out_dir = os.path.join(args.out_dir, args.group)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    skip_if_exists = args.resume
    yga = YahooGroupsAPI(args.group, args.cookie_t, args.cookie_y)
    if args.username:
        password = args.password or getpass.getpass()
        print "logging in..."
        if not yga.login(args.username, password):
            print "Login failed"
            sys.exit(1)

    if not (args.email or args.files or args.photos or args.database):
        args.email = args.files = args.photos = args.database = True

    with Mkchdir(args.group):
        if args.email:
            with Mkchdir('email'):
                archive_email(out_dir, yga, reattach=(not args.no_reattach),
                              save=(not args.no_save), skip_if_exists=skip_if_exists)
        if args.files:
            with Mkchdir('files'):
                archive_files(out_dir, yga, skip_if_exists=skip_if_exists)
        if args.photos:
            with Mkchdir('photos'):
                archive_photos(out_dir, yga, skip_if_exists=skip_if_exists)
        if args.database:
            with Mkchdir('databases'):
                archive_db(out_dir, yga, args.group, skip_if_exists=skip_if_exists)
