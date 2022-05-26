# Jellyfin Collection Iptv

jellyfin-collection-iptv Beta-v0.1

## Description
This tool will help you create a collection containing sub-collection of iptv channel by group-name (like in other iptv app).
- [ ] [Warning] I'm not responsible if you use this tool with illegal iptv provider.
- [ ] [Warning] All screenshot attached to this project displaying tv channel are linked to my own local setup and official legal paid subscription.

- Homepage with new iptv collection

![Collection-screen-homepage](https://github.com/dopch/Jellyfin-Collection-Iptv/blob/main/screenshots/1-collection-jellyfin.png)

- Sub-collections in iptv collection

![Subcollections](https://github.com/dopch/Jellyfin-Collection-Iptv/blob/main/screenshots/2-subcollection-jellyfin.png)

- Channels display from a sub-collections

![Channels-subcollection](https://github.com/dopch/Jellyfin-Collection-Iptv/blob/main/screenshots/3-subcollection-content-channels.png)



## Installation
- [ ] [Recommended] Create a python virtual env
- [ ] [Setup] pip install -r requirement.txt 

Tested with python 3.6 - 3.9 on Linux (should work on windows or on jellyfin inside docker container)


## Getting started
- [ ] [Warning] I'm not responsible if you use this tool with illegal iptv provider.



- [ ] [Import] From jellyfin LiveTv settings import your m3u (wait until 'Refresh guide end') 
- [ ] [Shutdown] Jellyfin server (systemctl stop jellyfin.service)
- [ ] [Backup] Your default library.db (in case of issue if you need to rollback)

## Usage
- [ ] [Launch] jellyfin_collections_inserter.py [-h] library_db default_folder data_folder cfolder_name m3u_file

Jellyfin collection creator

positional arguments:

  library_db      Full path of Jellyfin Library.db (jellyfin service need to in shutdown state).

  default_folder  Default folder full path (on linux /var/lib/jellyfin/root/default/)

  data_folder     Data folder full path (on linux /var/lib/jellyfin/data/)

  cfolder_name    Folder name where you want to store your channels (type collection)

  m3u_file        Full path of m3u file you want to insert

optional arguments:

  -h, --help      show this help message and exit


- [ ] [Example]  python jellyfin_collections_inserter.py /var/lib/jellyfin/data/library.db /var/lib/jellyfin/root/default/ /var/lib/jellyfin/data/ iptv /mnt/storage/iptv-m3u/latest-gen/local.m3u

- [ ] [Start] Jellyfin server (systemctl start jellyfin.service)
- [ ] [Homepage] will display you new collection (if you try to access it will return an empty collection)
- [ ] [Dashboard] Settings click 'Scan all libraries'
- [ ] [Homepage] Click on your newly created collection, everything should be sorted properly 

## Support
You can send me a message via email to jellyciptv@roottoor.eu

## Contributing
Idea and contribution are welcome

## License
https://github.com/globocom/m3u8 MIT License

https://github.com/pallets/jinja/blob/main/LICENSE.rst BSD 3-Clause "New" or "Revised" License

## Project status
Project is currently in beta.
