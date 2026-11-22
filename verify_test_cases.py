import json
import datetime
import unittest.mock as mock
from mrt_engine import ScheduleOptimizer, STATIONS_DB, TRAINS_DB

print("=" * 70)
print(f"📊 trtc_timetable.json 實際收錄總站數: {len(STATIONS_DB)} 個車站")
print(f"🚆 trtc_timetable.json 實際收錄總班次數: {len(TRAINS_DB)} 個真實列車班次")
print("=" * 70)

test_cases = [
    ("迴龍", "三和國中", "09:00"),
    ("民權西路", "士林", "09:00"),
    ("板橋", "淡水", "09:00"),
    ("松山", "動物園", "09:00"),
]

for title, mock_now in [
    ("【平日 (週一) 表定時刻實測】", datetime.datetime(2026, 11, 23, 9, 0)),
    ("【假日 (週日) 表定時刻實測】", datetime.datetime(2026, 11, 22, 9, 0)),
]:
    print(f"\n{title}")
    with mock.patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *args, **kw: datetime.datetime(*args, **kw)
        mock_dt.time = datetime.time

        for orig, dest, t_str in test_cases:
            plan = ScheduleOptimizer.calculate_transfer_plan(orig, dest, t_str)
            if not plan:
                print(f"  ❌ {orig} ➔ {dest} 規劃失敗")
                continue
            print(f"\n  🎯 {orig} ➔ {dest}（指定 {t_str} 出發）：")
            print(f"     • 表定時間: {plan['dep_time']} 發車 ➔ {plan['arr_time']} 抵達（總耗時 {plan['total_duration_min']} 分鐘）")
            print(f"     • 方案型態: {'直達班次' if plan['is_direct'] else '轉乘方案'}")
            for idx, leg in enumerate(plan["timeline"]):
                print(f"       段落 {idx+1}: {leg['line_name']} | {leg['dep_time']} {leg['from_station']} ➔ {leg['arr_time']} {leg['to_station']}")
            if plan.get("transfer_info"):
                print(f"       轉乘細節: {plan['transfer_info']['single_line_desc']}")

print("\n" + "=" * 70)
