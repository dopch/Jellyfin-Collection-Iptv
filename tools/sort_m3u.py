import re
import m3u8
import requests
import os
from m3u8 import protocol
from m3u8.parser import save_segment_custom_value


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


def clean_and_createdir():
    # Create latest-gen folder
    path = './latest-gen/'
    try:
        os.mkdir(path)
    except OSError as error:
        print(error)
    # Remove old sorted m3u
    for root, dirs, files in os.walk(path):
        for file in files:
            try:
                os.remove(os.path.join(root, file))
                print(f"{file} removed successfully")
            except OSError as error:
                print(error)
                print(f"{file} can not be removed")
    # Remove latest_unsorted.m3u
    try:
        os.remove('/latest_unsorted.m3u')
        print(f"./latest_unsorted removed successfully")
    except OSError as error:
        print(error)
        print(f"./latest_unsorted cannot be removed ")


def download_file(url,local_filename):
    with requests.get(url, stream=True, timeout=None, headers={"user-agent": "VLC/3.0.9 LibVLC/3.0.9"}) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return local_filename


def populate(e, provider_id):
    first_segment_props = e.custom_parser_values['extinf_props']
    if 'tvg-name' in first_segment_props.keys() and 'group-title' in first_segment_props.keys():
        type(first_segment_props)
        if first_segment_props['group-title'] == "":
            filename = './latest-gen/' + provider_id +'unclassified.m3u'
        else:
            path = './latest-gen/'
            filename = path + provider_id + (first_segment_props['group-title']).replace(' ', '_').replace('|', '')\
                .replace('/', '').replace('.', '').replace('-', '') + '.m3u'
        if 'tvg-logo' in first_segment_props.keys():
            entry = f"#EXTINF:-1 tvg-id=\"\" tvg-name=\"{first_segment_props['tvg-name']}\" tvg-logo=\"{first_segment_props['tvg-logo']}\" group-title=\"{first_segment_props['group-title']}\",{first_segment_props['tvg-name']}\n"
        else:
            entry = f"#EXTINF:-1 tvg-id=\"\" tvg-name=\"{first_segment_props['tvg-name']}\" group-title=\"{first_segment_props['group-title']}\",{first_segment_props['tvg-name']}\n"
        full_channel_entry = entry + e.uri + '\n'
        if os.path.exists(filename) is False:
            with open(filename, 'a') as f:
                f.write('#EXTM3U\n')
        with open(filename, 'a') as f:
                f.write(full_channel_entry)
    else:
        raise Exception(f"Sorry {e.uri} has no name or group")


def clean_unwanted():
    path = './latest-gen/'
    # Remove unwanted sorted m3u
    for root, dirs, files in os.walk(path):
        for file in files:
            try:
                chunk = file.split('_', 1)
                if chunk[1] in ['FR', 'BE', 'EN', 'US']:
                    print(file)
                else:
                    print('to be deleted', file)
                    os.remove(os.path.join(root, file))
                    print(f"{file} removed successfully")
            except OSError as error:
                print(error)
                print(f"{file} can not be removed")


def classify():
    clean_and_createdir()
    #local_filename = download_file('https://your-iptv-provider.m3u', 'latest_unsorted.m3u')
    playlist = m3u8._load_from_file('./latest_unsorted.m3u', custom_tags_parser=parse_iptv_attributes)
    for e in playlist.segments:
         populate(e, '1T_')
    clean_unwanted()


if __name__ == '__main__':
    classify()
