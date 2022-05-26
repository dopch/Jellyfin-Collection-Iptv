import datetime
import os
import sqlite3
import argparse
import uuid
import re
import m3u8
import random
from sys import platform
from os.path import exists
from m3u8 import protocol
from m3u8.parser import save_segment_custom_value
from jinja2 import Environment, FileSystemLoader


"""
Parse iptv attributes such as logo, group, name in m3u file
"""
def parse_iptv_attributes(line, lineno, data, state):
    # Customize parsing #EXTINF
    if line.startswith(protocol.extinf):
        title = ''
        chunks = line.replace(protocol.extinf + ':', '').split(',', 1)
        if len(chunks) == 2:
            duration_and_props, title = chunks
        elif len(chunks) == 1:
            duration_and_props = chunks[0]
        additional_props = {}
        chunks = duration_and_props.strip().split(' ', 1)
        if len(chunks) == 2:
            duration, raw_props = chunks
            matched_props = re.finditer(r'([\w\-]+)="([^"]*)"', line)
            for match in matched_props:
                additional_props[match.group(1)] = match.group(2)
        else:
            duration = duration_and_props
        if 'segment' not in state:
            state['segment'] = {}
        state['segment']['duration'] = float(duration)
        state['segment']['title'] = title
        # Helper function for saving custom values
        save_segment_custom_value(state, 'extinf_props', additional_props)
        # Tell 'main parser' that we expect an URL on next lines
        state['expect_segment'] = True
        # Tell 'main parser' that it can go to next line, we've parsed current fully.
        return True


def exec_sql_query(con, cur, query_str):
    if sqlite3.complete_statement(query_str):
        try:
            buffer = query_str.strip()
            cur.execute(buffer)
            # if its a select query display result
            if buffer.lstrip().upper().startswith("SELECT"):
                ret = cur.fetchall()
                return ret
            # if its an insert query commit to db
            if buffer.lstrip().upper().startswith("INSERT"):
                con.commit()
        except sqlite3.Error as e:
            print("An error occurred:", e.args[0])

"""
To make it usable on windows linux and osx
Format path for data and default folder for linux or windows, because one use / and the other \
"""
def platform_path(args: argparse.Namespace):
    if platform == "linux" or platform == "linux2" or platform == "darwin":
        if args.default_folder[-1] != '/':
            args.default_folder = args.default_folder + '/'
        if args.data_folder[-1] != '/':
            args.data_folder = args.data_folder + '/'
    elif platform == "win32":
        if args.default_folder[-1] != '\\':
            args.default_folder = args.default_folder + '\\'
        if args.data_folder[-1] != '/':
            args.data_folder = args.data_folder + '\\'
    return args


def write_to_disk(path, content):
    if os.path.exists(path) is False:
        with open(path, 'w') as f:
            f.write(content)


def check_guid(guid):
    if isinstance(guid, list) and len(guid) == 1 and isinstance(guid[0], tuple) and isinstance(guid[0][0],str):
        return guid[0][0]
    else:
        return -1


def check_subc_count(subc_count):
    if isinstance(subc_count, list) and len(subc_count) == 1 and isinstance(subc_count[0], tuple) and isinstance(subc_count[0][0],int):
        return subc_count[0][0]
    else:
        return -1


"""
RETURN LATEST CREATED channel between multiple channel with same name and same Sortname
example channel tv1 sortname 123-tv1 datecreated 01/01/2001 PresentationUniqueKey 42 and channel tv1 sortname 123-tv1 datecreated 01/01/2022 PresentationUniqueKey 43
ystem will return 43 because she is newer, in case of multiple sortname one from each will be return so we dont loose channel
"""
def check_channel_conflict(channel_name, con, cur):
    cpuks_clean = []
    sql_select_sortname_c = f"SELECT SortName,PresentationUniqueKey FROM TypedBaseItems WHERE UnratedType = 'LiveTvChannel' AND Name = \"{channel_name}\" ORDER BY DateCreated;"
    ret = exec_sql_query(con, cur, sql_select_sortname_c)
    for e in dict(ret).keys():
        cpuks_clean.append(dict(ret).get(e))
    return cpuks_clean


def populate_data_folder(key, d , data_folder, cfolder_name, con, cur):
    if platform == "linux" or platform == "linux2" or platform == "darwin":
        data_folder = data_folder + cfolder_name.lower() + '/' + key + " [boxset]" + '/'
    elif platform == "win32":
        data_folder = data_folder + cfolder_name.lower() + '\\' + key + " [boxset]"+ '\\'
    if exists(data_folder) is False:
        try:
            os.makedirs(data_folder)
        except Exception as error:
            print("Exeption in collection_folder makedirs data folder:", error)
    if exists(data_folder):
        channels = d.get(key)
        l_cpuk = []
        for channel in channels:
            sql_select_puk_c = f"SELECT PresentationUniqueKey FROM TypedBaseItems WHERE UnratedType = 'LiveTvChannel' AND Name = \"{channel}\";"
            cpuk = exec_sql_query(con,cur,sql_select_puk_c)
            if isinstance(cpuk, list) and len(cpuk) == 1 and isinstance(cpuk[0], tuple) and isinstance(cpuk[0][0], str):
                l_cpuk.append(cpuk[0][0])
            elif isinstance(cpuk, list) and len(cpuk) > 1:
                print(f"More than one channel with name = {channel} was found, by default newest one will be added to sub-collection")
                cpuk_clean = check_channel_conflict(channel, con, cur)
                for c in cpuk_clean:
                    l_cpuk.append(c)
            else:
                print(f"{channel} for subgroup {key} not found in library.db !")
        file_loader = FileSystemLoader('templates')
        env = Environment(loader=file_loader)
        template_collection_xml = env.get_template('data-collection/collection.xml')
        data_collection_xml = template_collection_xml.render(datetime_str=datetime.datetime.now().replace(microsecond=0), title_str=key, items=l_cpuk)
        local_collection_xml = data_folder + 'collection.xml'
        write_to_disk(local_collection_xml, data_collection_xml)


def check_sub_collection(subc_name, guid_collections, cfolder_data, con, cur):
    sql_count_subc = "SELECT COUNT(substr(hex(guid), 1, 32)) FROM TypedBaseItems WHERE type = 'MediaBrowser.Controller.Entities.Movies.BoxSet' AND ParentId = X'" + guid_collections + "' AND Name = '" + subc_name + "';"
    sql_select_guid_subc = "SELECT substr(hex(guid), 1, 32) FROM TypedBaseItems WHERE type = 'MediaBrowser.Controller.Entities.Movies.BoxSet' AND ParentId = X'" + guid_collections + "' AND Name = '" + subc_name + "';"
    subc_count = exec_sql_query(con, cur, sql_count_subc)
    subc_count = check_subc_count(subc_count)
    guid_subc = check_guid(exec_sql_query(con, cur, sql_select_guid_subc))
    if subc_count == 0:
        gen_guid_collection = uuid.uuid4().hex
        sql_insert_sub_collection = "INSERT INTO \"main\".\"TypedBaseItems\" (\"guid\", \"type\", \"data\", \"ParentId\", \"Path\", \"StartDate\", \"EndDate\", \"ChannelId\", \"IsMovie\", \"CommunityRating\", \"CustomRating\", \"IndexNumber\", \"IsLocked\", \"Name\", \"OfficialRating\", \"MediaType\", \"Overview\", \"ParentIndexNumber\", \"PremiereDate\", \"ProductionYear\", \"Genres\", \"SortName\", \"ForcedSortName\", \"RunTimeTicks\", \"DateCreated\", \"DateModified\", \"IsSeries\", \"EpisodeTitle\", \"IsRepeat\", \"PreferredMetadataLanguage\", \"PreferredMetadataCountryCode\", \"DateLastRefreshed\", \"DateLastSaved\", \"IsInMixedFolder\", \"LockedFields\", \"Studios\", \"Audio\", \"ExternalServiceId\", \"Tags\", \"IsFolder\", \"InheritedParentalRatingValue\", \"UnratedType\", \"TopParentId\", \"TrailerTypes\", \"CriticRating\", \"CleanName\", \"PresentationUniqueKey\", \"OriginalTitle\", \"PrimaryVersionId\", \"DateLastMediaAdded\", \"Album\", \"IsVirtualItem\", \"SeriesName\", \"UserDataKey\", \"SeasonName\", \"SeasonId\", \"SeriesId\", \"ExternalSeriesId\", \"Tagline\", \"ProviderIds\", \"Images\", \"ProductionLocations\", \"ExtraIds\", \"TotalBitrate\", \"ExtraType\", \"Artists\", \"AlbumArtists\", \"ExternalId\", \"SeriesPresentationUniqueKey\", \"ShowId\", \"OwnerId\", \"Width\", \"Height\", \"Size\") VALUES (X'" + gen_guid_collection + "', 'MediaBrowser.Controller.Entities.Movies.BoxSet', '{\"LocalTrailerIds\":[],\"RemoteTrailerIds\":[],\"DisplayOrder\":\"PremiereDate\",\"LibraryFolderIds\":[],\"IsRoot\":false,\"LinkedChildren\":[{\"Type\":\"Manual\",\"LibraryItemId\":\"887855df7761779c931e38a625f751bf\",\"ItemId\":\"887855df7761779c931e38a625f751bf\"},{\"Type\":\"Manual\",\"LibraryItemId\":\"3a952d7cea5c5d40fa1419ada9e9ac91\",\"ItemId\":\"3a952d7cea5c5d40fa1419ada9e9ac91\"}],\"DateLastSaved\":\"2022-04-29T14:00:25.9591689Z\",\"RemoteTrailers\":[],\"IsHD\":false,\"IsShortcut\":false,\"Width\":0,\"Height\":0,\"ExtraIds\":[],\"SupportsExternalTransfer\":false}', X'" + guid_collections.lower() + "', '%AppDataPath%/" + cfolder_data + "/" + subc_name + " [boxset]', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '1', '" + subc_name + "', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '" + subc_name + str(random.randrange(10000, 100000)) + "', NULL, NULL, '2022-04-29 13:59:22Z', '2022-04-29 13:59:22.5111606Z', NULL, NULL, NULL, NULL, NULL, '2022-04-29 14:00:25.9587387Z', '2022-04-29 14:00:25.9591689Z', '0', NULL, NULL, NULL, NULL, NULL, '1', '0', 'Movie', '8679d10569ec12981200c4116da3e90b', NULL, NULL, '" + subc_name + "', '1862bd9b40276363553619fc71558c45', NULL, NULL, NULL, NULL, '0', NULL, '1862bd9b-4027-6363-5536-19fc71558c45', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);"
        exec_sql_query(con, cur, sql_insert_sub_collection)
        guid_subc = check_guid(exec_sql_query(con, cur, sql_select_guid_subc))
        if guid_subc == gen_guid_collection.upper():
            print("sub collection insert succeeded ")
        else:
            print("sub collection insert failed ")
    else:
        if subc_name == "":
            print(f"collections {guid_collections} already contain collection unclassified with guid {guid_subc}")
        else:
            print(f"collections {guid_collections} already contain collection {subc_name} with guid {guid_subc}")


def populate_collection_folder(default_folder, data_folder, cfolder_name, subc_name):
    if platform == "linux" or platform == "linux2" or platform == "darwin":
        default_folder = default_folder + cfolder_name.lower().capitalize() + '/'
        data_folder = data_folder + cfolder_name.lower() + '/' + subc_name + " [boxset]" + '/'
    elif platform == "win32":
        default_folder = default_folder + cfolder_name.lower().capitalize() + '\\'
        data_folder = data_folder + cfolder_name.lower() + '\\' + subc_name + " [boxset]" + '\\'
    if exists(default_folder) is False:
        try:
            os.makedirs(default_folder)
        except Exception as error:
            print("Exeption in collection_folder makedirs default folder:", error)
    if exists(data_folder) is False:
        try:
            os.makedirs(data_folder)
        except Exception as error:
            print("Exeption in collection_folder makedirs data folder:", error)
    if exists(default_folder) and exists(data_folder):
        file_loader = FileSystemLoader('templates')
        env = Environment(loader=file_loader)
        template_boxsets_collection = env.get_template('default-collection/boxsets.collection')
        default_boxsets_collection = template_boxsets_collection.render()
        template_collection_mblink = env.get_template('default-collection/collections.mblink')
        default_collection_mblink = template_collection_mblink.render(cfolder_name_str=cfolder_name)
        template_option_xml = env.get_template('default-collection/options.xml')
        default_option_xml = template_option_xml.render(cfolder_name_str=cfolder_name)
        local_boxsets_collection = default_folder + 'boxsets.collection'
        local_collections_mblink = default_folder + 'collections.mblink'
        local_option_xml = default_folder + 'option.xml'
        write_to_disk(local_boxsets_collection, default_boxsets_collection)
        write_to_disk(local_collections_mblink, default_collection_mblink)
        write_to_disk(local_option_xml, default_option_xml)


def classify(args, guid_collections, cfolder_data, con, cur):
    playlist = m3u8._load_from_file(args.m3u_file, custom_tags_parser=parse_iptv_attributes)
    subc = []
# Create collection folder data and default populate default folder
    for e in playlist.segments:
        first_segment_props = e.custom_parser_values['extinf_props']
        if 'tvg-name' in first_segment_props.keys() and 'group-title' in first_segment_props.keys():
            if first_segment_props['group-title'] == "":
                populate_collection_folder(args.default_folder, args.data_folder, args.cfolder_name, 'unclassified')
                check_sub_collection('unclassified', guid_collections, cfolder_data, con, cur)
                if 'unclassified' not in subc:
                    subc.append('unclassified')
            else:
                populate_collection_folder(args.default_folder, args.data_folder, args.cfolder_name, first_segment_props['group-title'])
                check_sub_collection(first_segment_props['group-title'], guid_collections, cfolder_data, con, cur)
                if first_segment_props['group-title'] not in subc:
                    subc.append(first_segment_props['group-title'])
    # populate data template
    d = dict()
    for s in subc:
        for e in playlist.segments:
            first_segment_props = e.custom_parser_values['extinf_props']
            if 'tvg-name' in first_segment_props.keys() and 'group-title' in first_segment_props.keys():
                if first_segment_props['group-title'] == "" and s == 'unclassified':
                    if 'unclassified' not in d:
                        d['unclassified'] = list()
                        d['unclassified'].append(first_segment_props['tvg-name'])
                    else:
                        d['unclassified'].append(first_segment_props['tvg-name'])
                elif first_segment_props['group-title'] == s:
                    if s not in d:
                        d[s] = list()
                        d[s].append(first_segment_props['tvg-name'])
                    else:
                        d[s].append(first_segment_props['tvg-name'])
    for key in d.keys():
        populate_data_folder(key, d, args.data_folder, args.cfolder_name, con, cur)


def launch(args: argparse.Namespace):
    args = platform_path(args)
    if exists(args.library_db) is False:
        raise Exception(f"{args.library_db} does not exist")
    if exists(args.default_folder) is False:
        raise Exception(F"{args.default_folder} does not exit")
    if exists(args.data_folder) is False:
        raise Exception(F"{args.data_folder} does not exit")
    else:
        cfolder_default = args.cfolder_name.lower().capitalize()
        cfolder_data = args.cfolder_name.lower()
        sql_select_guid_root = "SELECT substr(hex(guid), 1, 32) FROM TypedBaseItems WHERE\
         type='MediaBrowser.Controller.Entities.AggregateFolder' AND Name='root';"
        sql_select_guid_media_folder = "SELECT substr(hex(guid), 1, 32) FROM TypedBaseItems WHERE\
         type='MediaBrowser.Controller.Entities.UserRootFolder' AND Name='Media Folders';"
        sql_select_guid_collections_folder = "SELECT substr(hex(guid), 1, 32) FROM TypedBaseItems\
                 WHERE type='MediaBrowser.Controller.Entities.CollectionFolder' AND Name='" + cfolder_default +"';"
        sql_select_guid_collections = "SELECT substr(hex(guid), 1, 32) FROM TypedBaseItems\
         WHERE type='MediaBrowser.Controller.Entities.Folder' AND\
          ParentId=(SELECT guid FROM TypedBaseItems WHERE type='MediaBrowser.Controller.Entities.AggregateFolder' AND\
           Name='root') AND Name='" + cfolder_data + "';"
        con = sqlite3.connect(args.library_db)
        cur = con.cursor()
        guid_root = check_guid(exec_sql_query(con, cur, sql_select_guid_root))
        guid_media_folder = check_guid(exec_sql_query(con, cur,sql_select_guid_media_folder))
        guid_collections_folder = check_guid(exec_sql_query(con, cur, sql_select_guid_collections_folder))
        guid_collections = check_guid(exec_sql_query(con, cur, sql_select_guid_collections))
        if guid_root == -1:
            raise Exception("guid_root was not found in db are you sure its a db from jellyfin (try to start jellyfin, go to dashboard and click scan all librairies)")
        if guid_media_folder == -1:
            raise Exception("guid_media_folder was not found in db are you sure its a db from jellyfin (try to start jellyfin, go to dashboard and click scan all librairies)")
        # Insert collections DEFAULT folder in db if not found
        if guid_collections_folder == -1:
            gen_guid_collections_folder = uuid.uuid4().hex
            print(f"No collection folder default found in {args.library_db} creating collections default folder with guid {gen_guid_collections_folder}")
            sql_insert_collections_folder = "INSERT INTO \"main\".\"TypedBaseItems\" (\"guid\", \"type\", \"data\", \"ParentId\", \"Path\", \"StartDate\", \"EndDate\", \"ChannelId\", \"IsMovie\", \"CommunityRating\", \"CustomRating\", \"IndexNumber\", \"IsLocked\", \"Name\", \"OfficialRating\", \"MediaType\", \"Overview\", \"ParentIndexNumber\", \"PremiereDate\", \"ProductionYear\", \"Genres\", \"SortName\", \"ForcedSortName\", \"RunTimeTicks\", \"DateCreated\", \"DateModified\", \"IsSeries\", \"EpisodeTitle\", \"IsRepeat\", \"PreferredMetadataLanguage\", \"PreferredMetadataCountryCode\", \"DateLastRefreshed\", \"DateLastSaved\", \"IsInMixedFolder\", \"LockedFields\", \"Studios\", \"Audio\", \"ExternalServiceId\", \"Tags\", \"IsFolder\", \"InheritedParentalRatingValue\", \"UnratedType\", \"TopParentId\", \"TrailerTypes\", \"CriticRating\", \"CleanName\", \"PresentationUniqueKey\", \"OriginalTitle\", \"PrimaryVersionId\", \"DateLastMediaAdded\", \"Album\", \"IsVirtualItem\", \"SeriesName\", \"UserDataKey\", \"SeasonName\", \"SeasonId\", \"SeriesId\", \"ExternalSeriesId\", \"Tagline\", \"ProviderIds\", \"Images\", \"ProductionLocations\", \"ExtraIds\", \"TotalBitrate\", \"ExtraType\", \"Artists\", \"AlbumArtists\", \"ExternalId\", \"SeriesPresentationUniqueKey\", \"ShowId\", \"OwnerId\", \"Width\", \"Height\", \"Size\") VALUES (X'"+ gen_guid_collections_folder + "', 'MediaBrowser.Controller.Entities.CollectionFolder', '{\"CollectionType\":\"boxsets\",\"PhysicalLocationsList\":[\"" + args.default_folder + "" + cfolder_default + "\",\"" + args.data_folder + "" + cfolder_data + "\"],\"PhysicalFolderIds\":[\"8679d10569ec12981200c4116da3e90b\"],\"IsRoot\":false,\"LinkedChildren\":[],\"DateLastSaved\":\"2022-04-29T13:59:22.4848253Z\",\"RemoteTrailers\":[],\"IsHD\":false,\"IsShortcut\":false,\"Width\":0,\"Height\":0,\"ExtraIds\":[],\"SupportsExternalTransfer\":false}', X'" + guid_media_folder.lower() + "', '" + args.default_folder + "" + cfolder_default + "', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '0', '" + cfolder_default + "', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '" + cfolder_data + "', NULL, NULL, '2022-04-29 13:59:22.3827521Z', '0001-01-01 00:00:00Z', NULL, NULL, NULL, NULL, NULL, '2022-04-29 13:59:22.4847553Z', '2022-04-29 13:59:22.4848253Z', '0', NULL, NULL, NULL, NULL, NULL, '1', '0', 'Other', NULL, NULL, NULL, '" + cfolder_data + "', '9d7ad6afe9afa2dab1a2f6e00ad28fa6', NULL, NULL, NULL, NULL, '0', NULL, '9d7ad6af-e9af-a2da-b1a2-f6e00ad28fa6', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);"
            exec_sql_query(con,cur, sql_insert_collections_folder)
            guid_collections_folder = check_guid(exec_sql_query(con, cur, sql_select_guid_collections_folder))
            if guid_collections_folder == gen_guid_collections_folder.upper():
                print("Collection folder insert succeeded")
            else:
                print("Collection folder insert failed")
        else:
            print(f"{args.library_db} already contain root {guid_root}, collection folder {args.default_folder}{cfolder_default} {guid_collections_folder})")
        # Insert collections folder in db if not found
        if guid_collections == -1:
            gen_guid_collections = uuid.uuid4().hex
            print(f"No collection found in {args.library_db} creating collections with guid {gen_guid_collections}")
            sql_insert_collections = "INSERT INTO \"main\".\"TypedBaseItems\" (\"guid\", \"type\", \"data\", \"ParentId\", \"Path\", \"StartDate\", \"EndDate\", \"ChannelId\", \"IsMovie\", \"CommunityRating\", \"CustomRating\", \"IndexNumber\", \"IsLocked\", \"Name\", \"OfficialRating\", \"MediaType\", \"Overview\", \"ParentIndexNumber\", \"PremiereDate\", \"ProductionYear\", \"Genres\", \"SortName\", \"ForcedSortName\", \"RunTimeTicks\", \"DateCreated\", \"DateModified\", \"IsSeries\", \"EpisodeTitle\", \"IsRepeat\", \"PreferredMetadataLanguage\", \"PreferredMetadataCountryCode\", \"DateLastRefreshed\", \"DateLastSaved\", \"IsInMixedFolder\", \"LockedFields\", \"Studios\", \"Audio\", \"ExternalServiceId\", \"Tags\", \"IsFolder\", \"InheritedParentalRatingValue\", \"UnratedType\", \"TopParentId\", \"TrailerTypes\", \"CriticRating\", \"CleanName\", \"PresentationUniqueKey\", \"OriginalTitle\", \"PrimaryVersionId\", \"DateLastMediaAdded\", \"Album\", \"IsVirtualItem\", \"SeriesName\", \"UserDataKey\", \"SeasonName\", \"SeasonId\", \"SeriesId\", \"ExternalSeriesId\", \"Tagline\", \"ProviderIds\", \"Images\", \"ProductionLocations\", \"ExtraIds\", \"TotalBitrate\", \"ExtraType\", \"Artists\", \"AlbumArtists\", \"ExternalId\", \"SeriesPresentationUniqueKey\", \"ShowId\", \"OwnerId\", \"Width\", \"Height\", \"Size\") VALUES (X'" + gen_guid_collections + "', 'MediaBrowser.Controller.Entities.Folder', '{\"IsRoot\":false,\"LinkedChildren\":[],\"DateLastSaved\":\"2022-04-29T13:59:22.4349264Z\",\"RemoteTrailers\":[],\"IsHD\":false,\"IsShortcut\":false,\"Width\":0,\"Height\":0,\"ExtraIds\":[],\"SupportsExternalTransfer\":false}', X'" + guid_root.lower() + "', '%AppDataPath%/" + cfolder_data + "', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '0', '" + cfolder_data + "', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '" + cfolder_data + "', NULL, NULL, '2022-04-28 00:34:56.6478546Z', '0001-01-01 00:00:00Z', NULL, NULL, NULL, NULL, NULL, '2022-04-29 13:59:22.4349038Z', '2022-04-29 13:59:22.4349264Z', '0', NULL, NULL, NULL, NULL, NULL, '1', '0', 'Other', '8679d10569ec12981200c4116da3e90b', NULL, NULL, '" + cfolder_data + "', '8679d10569ec12981200c4116da3e90b', NULL, NULL, NULL, NULL, '0', NULL, '8679d105-69ec-1298-1200-c4116da3e90b', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);"
            exec_sql_query(con, cur, sql_insert_collections)
            guid_collections = check_guid(exec_sql_query(con, cur, sql_select_guid_collections))
            if guid_collections == gen_guid_collections.upper():
                print("collections insert succeeded ")
            else:
                print("collections insert failed ")
        else:
            print(f"{args.library_db} already contain root {guid_root}, collection folder {args.default_folder}{cfolder_default} {guid_collections_folder}, collections {args.data_folder}{cfolder_data} {guid_collections}")
        classify(args, guid_collections, cfolder_data, con, cur)
        con.close()


"""
Init argparse and define argument for project
"""
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Jellyfin collection creator")
    parser.add_argument('library_db', type=str, help="Full path of Jellyfin Library.db (jellyfin service need to in shutdown state).")
    parser.add_argument('default_folder', type=str, help="Default folder full path (on linux /var/lib/jellyfin/root/default/)")
    parser.add_argument('data_folder', type=str, help="Data folder full path (on linux /var/lib/jellyfin/data/)")
    parser.add_argument('cfolder_name', type=str, help="Folder name where you want to store your channels (type collection)")
    parser.add_argument('m3u_file', type=str, help="Full path of m3u file you want to insert")
    args = parser.parse_args()
    launch(args)
