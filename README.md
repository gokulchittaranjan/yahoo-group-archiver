yahoo-group-archiver
====================

This fork adds the ability to resume the downloads from where it failed (add --resume switch to the ./yahoo.py command). It also silently handles errors downloading messages/files so that it doesn't crash the script due to the random errors.

**Note:** Yahoo now have a ["Get My Data" tool](https://groups.yahoo.com/neo/getmydata)
available, which may provide an alternative to this tool, although it was not working at the time
of writing.

This tool archives a Yahoo group using the non-public API used by the Yahoo Groups website UI.

Features:
* Saves full email content
* Fetches email attachments and recombines with email
* Downloads attachments as separate files
* Fetch all files
* Fetch all photos
* Fetch all database tables

Requirements:
* Python 2.7
* Requests library

Usage:
```bash
pip install requests
./yahoo.py -u "<username>" -ct "<T_cookie>" -cy "<Y_cookie>" "<groupid>"
```

Where <username> is your Yahoo username or full login email address.

You will need to get the `T` and `Y` cookie values from an authenticated
browser session.
In Google Chrome these steps are required:
1. Go to [Yahoo Groups](https://groups.yahoo.com/neo).
2. Click the ⓘ (cicled letter i) in the address bar.
3. Click "Cookies".
4. On the Allowed tab select "Yahoo.com" followed by "Cookies" in the tree listing.
5. Select the T cookie and copy the Content field in place of <T_cookie> in the above command line.
6. Select the Y cookie and copy the Content field in place of <Y_cookie> in the above command line.

Note: the string you paste _must_ be surrounded by quotes.

Files will be placed into the directory structure groupname/{email,files,photos,databases}
