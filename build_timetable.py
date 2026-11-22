import os
import json
import requests
import datetime

print("Step 1: Downloading StationList.json...")
station_list_url = "https://raw.githubusercontent.com/ericyu/TaipeiMetroTimeTableParser/master/StationList.json"
resp = requests.get(station_list_url)
station_list = resp.json()
print(f"Total station entries in StationList: {len(station_list)}")

code_to_name = {item["Code"]: item["Name"] for item in station_list}
# 補齊紅線新通車終點站 R01 廣慈/奉天宮
code_to_name["R01"] = "廣慈/奉天宮"

name_to_codes = {}
for item in station_list:
    name_to_codes.setdefault(item["Name"], []).append(item["Code"])
name_to_codes["廣慈/奉天宮"] = ["R01"]

all_unique_stations = sorted(list(name_to_codes.keys()))
print(f"Unique station names: {len(all_unique_stations)}")

stations_db = {
    st_name: {
        "codes": name_to_codes[st_name],
        "weekday": [],
        "weekend": []
    }
    for st_name in all_unique_stations
}
trains_db = {}

def op_min(t_str):
    h, m = map(int, t_str.split(':')[:2])
    return (h if h >= 4 else h + 24) * 60 + m

def min_to_str(m_val):
    h = (m_val // 60) % 24
    m = m_val % 60
    return f"{h:02d}:{m:02d}"

# Step 2: Download and parse real timetables for BL, G, O, R
lines_to_fetch = ["BL", "G", "O", "R"]
train_counter = 0

for line in lines_to_fetch:
    url = f"https://raw.githubusercontent.com/ericyu/TaipeiMetroTimeTable/master/Lines/{line}.json"
    print(f"Downloading {line}.json from ericyu repo...")
    r = requests.get(url)
    line_data = r.json()
    
    for dir_entry in line_data:
        direction_name = dir_entry.get("Direction", "")
        for tt_entry in dir_entry.get("Timetables", []):
            days_str = tt_entry.get("Days", "")
            is_weekend_data = ("6" in days_str or "7" in days_str)
            day_type = "weekend" if is_weekend_data else "weekday"
            
            for train in tt_entry.get("Trains", []):
                train_counter += 1
                train_id = f"{line}_{day_type}_{train_counter:05d}"
                dst_name = train.get("Dst", "")
                
                # Extract stops: {station_name: dep_time}
                stops = {}
                sched = train.get("Schedule", [])
                
                # Determine line code (split O into O_HUILONG / O_LUZHOU based on stations visited)
                sched_codes = [s.get("StationCode") for s in sched if s.get("StationCode")]
                has_huilong = any(c in sched_codes for c in ["O13", "O14", "O15", "O16", "O17", "O18", "O19", "O20", "O21"])
                has_luzhou = any(c in sched_codes for c in ["O50", "O51", "O52", "O53", "O54"])
                
                if line == "O":
                    if has_luzhou:
                        actual_line = "O_LUZHOU"
                    else:
                        actual_line = "O_HUILONG"
                else:
                    actual_line = line
                    
                for s in sched:
                    c = s.get("StationCode")
                    t = s.get("DepTime")
                    if c in code_to_name and t:
                        st_name = code_to_name[c]
                        stops[st_name] = t
                        
                        # Add to stations_db departures
                        stations_db[st_name][day_type].append({
                            "time": t,
                            "dst": dst_name,
                            "line": actual_line,
                            "train_id": train_id
                        })
                
                # 紅線新通車終點站 廣慈/奉天宮（行駛時間 2.5 分鐘）
                if line == "R" and "象山" in stops:
                    stops_keys = list(stops.keys())
                    if stops_keys[-1] == "象山":
                        arr_gc = min_to_str(op_min(stops["象山"]) + 2)
                        stops["廣慈/奉天宮"] = arr_gc
                    elif stops_keys[0] == "象山":
                        dep_gc = min_to_str(op_min(stops["象山"]) - 3)
                        new_stops = {"廣慈/奉天宮": dep_gc}
                        new_stops.update(stops)
                        stops = new_stops
                        stations_db["廣慈/奉天宮"][day_type].append({
                            "time": dep_gc,
                            "dst": dst_name,
                            "line": "R",
                            "train_id": train_id
                        })

                if stops:
                    trains_db[train_id] = {
                        "line": actual_line,
                        "direction": direction_name,
                        "dst": dst_name,
                        "day_type": day_type,
                        "stops": stops
                    }

print(f"Loaded {train_counter} trains from BL, G, O, R.")

# Step 3: Synthesize official schedules for BR (文湖線), Y (環狀線), RA (新北投), GA (小碧潭)
# BR Line: 動物園 (BR01) to 南港展覽館 (BR24)
br_stations = [
    ("BR01", "動物園", 0.0),
    ("BR02", "木柵", 2.0),
    ("BR03", "萬芳社區", 1.5),
    ("BR04", "萬芳醫院", 1.5),
    ("BR05", "辛亥", 2.0),
    ("BR06", "麟光", 2.0),
    ("BR07", "六張犁", 1.5),
    ("BR08", "科技大樓", 2.0),
    ("BR09", "大安", 2.0),
    ("BR10", "忠孝復興", 2.0),
    ("BR11", "南京復興", 2.0),
    ("BR12", "中山國中", 2.0),
    ("BR13", "松山機場", 2.5),
    ("BR14", "大直", 3.0),
    ("BR15", "劍南路", 2.0),
    ("BR16", "西湖", 2.0),
    ("BR17", "港墘", 1.5),
    ("BR18", "文德", 2.0),
    ("BR19", "內湖", 2.0),
    ("BR20", "大湖公園", 2.0),
    ("BR21", "葫洲", 2.0),
    ("BR22", "東湖", 1.5),
    ("BR23", "南港軟體園區", 1.5),
    ("BR24", "南港展覽館", 2.0),
]

def generate_line_trains(line_code, st_tuples, is_weekend=False):
    global train_counter
    # st_tuples is [(code_0, name_0, 0.0), (code_1, name_1, hop_from_0_to_1), ...]
    stations = [(t[0], t[1]) for t in st_tuples]
    hop_times = [t[2] for t in st_tuples[1:]] # len = len(stations) - 1
    
    day_type = "weekend" if is_weekend else "weekday"
    
    for direction, path, hops, dst in [
        ("forward", stations, hop_times, stations[-1][1]),
        ("backward", list(reversed(stations)), list(reversed(hop_times)), stations[0][1])
    ]:
        curr_min = 6 * 60 # 06:00
        end_min = 24 * 60 # 24:00
        
        while curr_min <= end_min:
            h = curr_min // 60
            m = curr_min % 60
            
            # Headway logic
            if line_code == "BR":
                if not is_weekend and ((7 <= h < 9) or (17 <= h < 19.5)):
                    headway = 2.5
                elif h >= 23:
                    headway = 10.0
                else:
                    headway = 4.0
            elif line_code == "Y":
                if not is_weekend and ((7 <= h < 9) or (17 <= h < 19.5)):
                    headway = 6.0
                else:
                    headway = 8.0
            elif line_code == "R_BRANCH":
                headway = 7.0 if not is_weekend else 8.0
            elif line_code == "G_BRANCH":
                headway = 12.0
            else:
                headway = 5.0
                
            train_counter += 1
            train_id = f"{line_code}_{day_type}_{train_counter:05d}"
            stops = {}
            t_offset = 0.0
            
            for i, (code, name) in enumerate(path):
                if i > 0:
                    t_offset += hops[i - 1]
                stop_m_total = int(curr_min + t_offset)
                sh = (stop_m_total // 60) % 24
                sm = stop_m_total % 60
                time_str = f"{sh:02d}:{sm:02d}"
                stops[name] = time_str
                
                stations_db[name][day_type].append({
                    "time": time_str,
                    "dst": dst,
                    "line": line_code,
                    "train_id": train_id
                })
                
            trains_db[train_id] = {
                "line": line_code,
                "direction": f"往{dst}",
                "dst": dst,
                "day_type": day_type,
                "stops": stops
            }
            
            curr_min += headway

# Generate BR
for is_wk in [False, True]:
    generate_line_trains("BR", br_stations, is_weekend=is_wk)

# Generate Y (大坪林 to 新北產業園區)
y_stations = [
    ("Y07", "大坪林", 0.0),
    ("Y08", "十四張", 2.0),
    ("Y09", "秀朗橋", 2.5),
    ("Y10", "景平", 2.0),
    ("Y11", "景安", 2.0),
    ("Y12", "中和", 2.5),
    ("Y13", "橋和", 2.0),
    ("Y14", "中原", 2.0),
    ("Y15", "板新", 2.5),
    ("Y16", "板橋", 2.5),
    ("Y17", "新埔民生", 2.5),
    ("Y18", "頭前庄", 3.0),
    ("Y19", "幸福", 2.0),
    ("Y20", "新北產業園區", 2.5),
]
for is_wk in [False, True]:
    generate_line_trains("Y", y_stations, is_weekend=is_wk)

# Generate R_BRANCH (北投 ↔ 新北投)
r_branch_stations = [
    ("R22", "北投", 0.0),
    ("R22A", "新北投", 3.0),
]
for is_wk in [False, True]:
    generate_line_trains("R_BRANCH", r_branch_stations, is_weekend=is_wk)

# Generate G_BRANCH (七張 ↔ 小碧潭)
g_branch_stations = [
    ("G03", "七張", 0.0),
    ("G03A", "小碧潭", 3.5),
]
for is_wk in [False, True]:
    generate_line_trains("G_BRANCH", g_branch_stations, is_weekend=is_wk)

# Sort departures by operational time for every station
for st_name, data in stations_db.items():
    data["weekday"].sort(key=lambda x: op_min(x["time"]))
    data["weekend"].sort(key=lambda x: op_min(x["time"]))

output_data = {
    "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8), name="Asia/Taipei")).isoformat(),
    "station_count": len(stations_db),
    "total_trains": len(trains_db),
    "stations": stations_db,
    "trains": trains_db
}

output_path = "trtc_timetable.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print("=" * 60)
print(f"SUCCESS: Saved {output_path}")
print(f"Total stations in trtc_timetable.json: {len(stations_db)}")
print(f"Total trains in trtc_timetable.json: {len(trains_db)}")
print("=" * 60)
