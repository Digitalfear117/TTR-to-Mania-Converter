import xml.etree.ElementTree as ET
import re

def parse_xml(file_path):
    # Load and parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()

    uid_map = {}
    objects = []
    metadata = {'title': None, 'artist': None}

    # Find the array of objects (should be under $objects key)
    for dict_elem in root.findall(".//dict"):
        elements = list(dict_elem)
        for idx, elem in enumerate(elements):
            if elem.tag == 'key' and elem.text == '$objects':
                # The value is the element immediately after the key
                if idx + 1 < len(elements):
                    value_elem = elements[idx + 1]
                    if value_elem.tag == 'array':
                        objects = value_elem.findall('./*')
                        break
        if objects:
            break

    # Build the UID map with parsed dictionaries
    for idx, obj in enumerate(objects):
        if obj.tag == 'string':
            # Extract title and artist from string elements
            text = obj.text
            if text.startswith('TITLE:'):
                metadata['title'] = text[len('TITLE:'):].strip()
            elif text.startswith('ARTIST:'):
                metadata['artist'] = text[len('ARTIST:'):].strip()
        else:
            uid_map[idx] = parse_dict(obj)

    return uid_map, metadata

def parse_dict(element):
    """Recursively parse a dict element into a Python dictionary."""
    result = {}
    elements = list(element)
    idx = 0
    while idx < len(elements):
        key_elem = elements[idx]
        if key_elem.tag == 'key':
            key = key_elem.text
            idx += 1
            if idx < len(elements):
                value_elem = elements[idx]
                value = parse_value(value_elem)
                result[key] = value
        idx += 1
    return result

def parse_value(value_elem):
    """Parse a value element based on its type."""
    if value_elem.tag == 'dict':
        return parse_dict(value_elem)
    elif value_elem.tag == 'array':
        return parse_array(value_elem)
    elif value_elem.tag == 'integer':
        return int(value_elem.text)
    elif value_elem.tag == 'real':
        return float(value_elem.text)
    elif value_elem.tag == 'string':
        return value_elem.text
    elif value_elem.tag == 'true':
        return True
    elif value_elem.tag == 'false':
        return False
    elif value_elem.tag == 'data':
        return value_elem.text  # Handle base64-encoded data if needed
    else:
        return value_elem.text  # Fallback for any other types

def parse_array(element):
    """Parse an array element into a list."""
    result = []
    for item in element:
        value = parse_value(item)
        result.append(value)
    return result

def resolve_references(obj, uid_map):
    """Recursively resolve CF$UID references in the parsed data."""
    if isinstance(obj, dict):
        if 'CF$UID' in obj:
            uid = int(obj['CF$UID'])
            if uid in uid_map:
                resolved_obj = uid_map[uid]
                # Recursively resolve the resolved_obj
                return resolve_references(resolved_obj, uid_map)
            else:
                print(f"UID {uid} not found in uid_map")
                return None
        else:
            # Recursively resolve each value
            resolved_dict = {}
            for key, value in obj.items():
                resolved_value = resolve_references(value, uid_map)
                resolved_dict[key] = resolved_value
            return resolved_dict
    elif isinstance(obj, list):
        # Recursively resolve each item
        resolved_list = [resolve_references(item, uid_map) for item in obj]
        return resolved_list
    else:
        # Return the object as is
        return obj

def extract_track_ids(uid_map):
    track_ids = []
    for uid, obj in uid_map.items():
        if isinstance(obj, dict):
            if 'trackID' in obj:
                track_id = int(obj['trackID'])
                if track_id not in track_ids:
                    track_ids.append(track_id)
                    print(f"Found track ID: {track_id}")
    return track_ids

def extract_notes_for_track(uid_map, target_track_id):
    notes = []
    for uid, obj in uid_map.items():
        if isinstance(obj, dict) and 'trackID' in obj:
            track_id = int(obj['trackID'])
            if track_id == target_track_id:
                print(f"Found track dict for track ID {track_id}")
                # Resolve references in the track dict
                track_dict = resolve_references(obj, uid_map)
                # Extract notes from this track
                track_notes = extract_notes_from_track(track_dict, uid_map)
                notes.extend(track_notes)
    return notes

def extract_notes_from_track(track_dict, uid_map):
    notes = []
    # Get the tracks
    tracks = track_dict.get('tracks')
    if tracks:
        tracks = resolve_references(tracks, uid_map)
        if isinstance(tracks, dict):
            tracks_list = tracks.get('NS.objects', [])
            print(f"Tracks list: {tracks_list}")
            for midi_track in tracks_list:
                midi_track = resolve_references(midi_track, uid_map)
                if midi_track:
                    print(f"Processing midi track")
                    # Extract notes from midi_track
                    midi_notes = extract_notes_from_midi_track(midi_track, uid_map)
                    notes.extend(midi_notes)
        elif isinstance(tracks, list):
            for midi_track in tracks:
                midi_track = resolve_references(midi_track, uid_map)
                if midi_track:
                    print(f"Processing midi track")
                    # Extract notes from midi_track
                    midi_notes = extract_notes_from_midi_track(midi_track, uid_map)
                    notes.extend(midi_notes)
        else:
            print("No tracks found in track_dict.")
    else:
        print("No tracks key in track_dict.")
    return notes

def extract_notes_from_midi_track(midi_track_dict, uid_map):
    notes = []
    # Get the events
    events = midi_track_dict.get('events')
    if events:
        events = resolve_references(events, uid_map)
        if isinstance(events, dict):
            events_list = events.get('NS.objects', [])
            print(f"Events list: {events_list}")
            for note in events_list:
                note = resolve_references(note, uid_map)
                if note:
                    note_data = extract_note_data(note, uid_map)
                    if note_data:
                        notes.append(note_data)
        elif isinstance(events, list):
            for note in events:
                note = resolve_references(note, uid_map)
                if note:
                    note_data = extract_note_data(note, uid_map)
                    if note_data:
                        notes.append(note_data)
        else:
            print("No events found in midi_track_dict.")
    else:
        print("No events key in midi_track_dict.")
    return notes

def extract_note_data(note_dict, uid_map):
    # Note: 'note_dict' should already be resolved
    if not isinstance(note_dict, dict):
        return None
    note_data = {}
    if 'note' in note_dict:
        note_data['note'] = int(note_dict['note'])
    else:
        return None  # 'note' is essential
    if 'time' in note_dict:
        note_data['time'] = float(note_dict['time'])
    else:
        return None  # 'time' is essential
    if 'type' in note_dict:
        note_data['type'] = int(note_dict['type'])
    else:
        return None  # 'type' is essential
    if 'timeInQuarterNotes' in note_dict:
        note_data['time_in_qn'] = float(note_dict['timeInQuarterNotes'])
    else:
        return None  # 'timeInQuarterNotes' is essential
    if 'text' in note_dict:
        # Resolve the text reference
        text_value = resolve_references(note_dict['text'], uid_map)
        if isinstance(text_value, str):
            note_data['text'] = text_value
    return note_data

# Define the threshold for hold notes (in quarter notes)
THRESHOLD_QN = 2.5  # Adjust as needed

def process_notes(notes):
    """Process the notes to determine if they are tap or hold notes based on duration in quarter notes."""
    events = []
    note_starts = {}

    for note in notes:
        note_number = note['note']
        note_time = note['time']
        note_type = note['type']
        time_in_qn = note['time_in_qn']

        if note_type == 0:
            # Note start
            note_starts[(note_number, note_time)] = note
        elif note_type == 1:
            # Note end
            # Find the matching start note with the same note number
            matching_key = None
            for key in note_starts.keys():
                if key[0] == note_number:
                    matching_key = key
                    break

            if matching_key:
                matching_start = note_starts.pop(matching_key)
                duration = note_time - matching_start['time']
                duration_qn = time_in_qn - matching_start['time_in_qn']
                # Use duration in quarter notes to classify tap vs hold
                event_type = 'tap' if duration_qn <= THRESHOLD_QN else 'hold'
                event = {
                    'note': note_number,
                    'start_time': matching_start['time'],
                    'end_time': note_time,
                    'duration': duration,
                    'type': event_type
                }
                events.append(event)
            else:
                print(f"Warning: Note end {note_number} at time {note_time} without matching start")
        else:
            # Skip meta events or unknown types
            continue

    # Handle any note starts that have no matching ends (these are tap notes)
    for note_key, start_note in note_starts.items():
        note_time = start_note['time']
        event = {
            'note': start_note['note'],
            'start_time': note_time,
            'end_time': note_time,
            'duration': 0,
            'type': 'tap'
        }
        events.append(event)

    # Sort events by start time
    events.sort(key=lambda x: x['start_time'])

    return events

def generate_osu_file(events, metadata, difficulty_name):
    """Generate the osu!mania map file for a specific difficulty."""
    # Construct the file name using the osu! file naming convention
    artist = metadata.get('artist', 'Unknown Artist')
    title = metadata.get('title', 'Unknown Title')
    creator = 'Tapulous'

    # Sanitize file name to remove any invalid characters
    def sanitize_filename(name):
        return re.sub(r'[\\/*?:"<>|]', "", name)

    artist = sanitize_filename(artist)
    title = sanitize_filename(title)
    difficulty_name = sanitize_filename(difficulty_name)

    file_name = f"{artist} - {title} ({creator}) [{difficulty_name}].osu"

    with open(file_name, 'w') as f:
        write_osu_header(f, metadata, difficulty_name)

        # Define mapping for note integer values to osu!mania lanes (X positions)
        note_to_column = {
            60: 0,     # Left column
            62: 256,   # Middle column
            64: 512    # Right column
        }

        for event in events:
            note_number = event['note']
            x_pos = note_to_column.get(note_number, -1)
            if x_pos == -1:
                continue  # Skip notes that are not mapped

            start_time_ms = convert_to_osu_timing(event['start_time'])

            if event['type'] == 'tap':
                # Tap note
                f.write(f"{x_pos},192,{start_time_ms},1,0,0:0:0:0:\n")
            elif event['type'] == 'hold':
                # Hold note
                end_time_ms = convert_to_osu_timing(event['end_time'])
                f.write(f"{x_pos},192,{start_time_ms},128,0,{int(end_time_ms)}:0:0:0:0:\n")

def write_osu_header(f, metadata, difficulty_name):
    """Write the standard osu file header to each file."""
    title = metadata.get('title', 'Unknown Title')
    artist = metadata.get('artist', 'Unknown Artist')
    creator = 'Tapulous'

    f.write("osu file format v14\n\n")
    f.write("[General]\n")
    f.write("AudioFilename: audio.mp3\n")
    f.write("AudioLeadIn: 0\n")
    f.write("PreviewTime: -1\n")
    f.write("Countdown: 0\n")
    f.write("SampleSet: Normal\n")
    f.write("StackLeniency: 0.7\n")
    f.write("Mode: 3\n")
    f.write("LetterboxInBreaks: 0\n\n")

    f.write("[Editor]\n")
    f.write("DistanceSpacing: 1.0\n")
    f.write("BeatDivisor: 4\n")
    f.write("GridSize: 4\n")
    f.write("TimelineZoom: 1.0\n\n")

    f.write("[Metadata]\n")
    f.write(f"Title:{title}\n")
    f.write(f"TitleUnicode:{title}\n")
    f.write(f"Artist:{artist}\n")
    f.write(f"ArtistUnicode:{artist}\n")
    f.write(f"Creator:{creator}\n")
    f.write(f"Version:{difficulty_name}\n")
    f.write("Source:Tap Tap Revenge\n")
    f.write("Tags:\n")
    f.write("BeatmapID:0\n")
    f.write("BeatmapSetID:-1\n\n")

    f.write("[Difficulty]\n")
    f.write("HPDrainRate:5\n")
    f.write("CircleSize:3\n")  # Adjusted for 3K osu!mania
    f.write("OverallDifficulty:5\n")
    f.write("ApproachRate:5\n")
    f.write("SliderMultiplier:1.4\n")
    f.write("SliderTickRate:1\n\n")

    f.write("[Events]\n")
    f.write("//Background and Video events\n\n")

    f.write("[TimingPoints]\n")
    f.write("0,267.857142857143,4,1,0,100,1,0\n\n")

    f.write("[HitObjects]\n")

def convert_to_osu_timing(time):
    """Convert time from seconds to milliseconds for osu!mania."""
    return int(time * 1000)

def main():
    # Path to the input XML file
    input_file = "taptrack.ttr2_track.xml"  # Update this path if necessary

    # Parse the XML to build the UID map and extract metadata
    uid_map, metadata = parse_xml(input_file)
    print(f"Number of items in uid_map: {len(uid_map)}")
    print(f"Extracted metadata: {metadata}")

    # Extract all available track IDs (difficulties)
    track_ids = extract_track_ids(uid_map)
    print(f"Available track IDs: {track_ids}")

    # Process each difficulty separately
    for track_id in track_ids:
        print(f"Processing track ID: {track_id}")
        notes = extract_notes_for_track(uid_map, track_id)
        if not notes:
            print(f"No notes found for track ID {track_id}")
            continue
        events = process_notes(notes)
        difficulty_name = f"Difficulty_{track_id}"
        generate_osu_file(events, metadata, difficulty_name)
        print(f"Generated osu file for track ID {track_id}.")

if __name__ == "__main__":
    main()