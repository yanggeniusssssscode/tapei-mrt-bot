import random
import datetime
import unittest.mock as mock
from mrt_engine import ScheduleOptimizer, STATIONS_DB, TRAINS_DB

print("=" * 75)
print(f"📊 trtc_timetable.json 全線資料庫收錄: {len(STATIONS_DB)} 個車站 | {len(TRAINS_DB)} 個真實列車班次")
print("=" * 75)

# 1. 核心指定驗收題目
required_tests = [
    ("迴龍", "民權西路", "直達（0 次轉乘）"),
    ("迴龍", "三和國中", "轉乘 1 次（大橋頭同月台 0 分鐘）"),
    ("三和國中", "新北投", "轉乘 2 次（民權西路 ➔ 北投）"),
]

# 2. 隨機選取 5 組冷門跨線起迄點
all_stations = list(STATIONS_DB.keys())
random.seed(42) # 固定種子確保可重現，或選取不同線路冷門起迄點
sample_candidates = [
    ("新北產業園區", "動物園", "環狀線 ➔ 文湖線（跨 3 線）"),
    ("頂埔", "淡水", "板南線最南端 ➔ 淡水信義線最北端"),
    ("南港軟體園區", "迴龍", "文湖線 ➔ 中和新蘆迴龍線"),
    ("幸福", "小碧潭", "環狀線 ➔ 松山新店小碧潭支線"),
    ("蘆洲", "象山", "中和新蘆蘆洲線 ➔ 淡水信義線最南端"),
]

def run_tests_for_date(date_label, test_dt):
    print(f"\n==================== {date_label}（模擬出發時間 09:00）====================")
    with mock.patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = test_dt
        mock_dt.side_effect = lambda *args, **kw: datetime.datetime(*args, **kw)
        mock_dt.time = datetime.time

        all_tests = [(orig, dest, desc) for orig, dest, desc in required_tests] + sample_candidates
        
        for idx, (orig, dest, desc) in enumerate(all_tests, 1):
            plan = ScheduleOptimizer.calculate_transfer_plan(orig, dest, "09:00")
            print(f"\n【測資 {idx}】{orig} ➔ {dest} ({desc})")
            if not plan:
                print("  ❌ 規劃失敗！查無路徑或班次。")
                continue
                
            transfers_count = len(plan["segments"]) - 1
            print(f"  • 表定乘車: {plan['dep_time']} 發車 ➔ {plan['arr_time']} 抵達（總耗時 {plan['total_duration_min']} 分鐘）")
            print(f"  • 轉乘次數: {transfers_count} 次轉乘（共 {len(plan['segments'])} 段車程）")
            
            for seg_idx, seg in enumerate(plan["segments"], 1):
                print(f"    第 {seg_idx} 段: 【{seg['line_name']}】{seg['dep_time']} {seg['from_station']} ➔ {seg['arr_time']} {seg['to_station']} (約 {seg['stations_count']} 站，往 {seg['dst']})")
                if seg.get("transfer_after"):
                    print(f"       ⤷ 轉乘資訊: {seg['transfer_after']['desc']}")

# 執行平日與假日完整驗證
run_tests_for_date("平日 (週一) 官方表定班表驗測", datetime.datetime(2026, 11, 23, 9, 0))
run_tests_for_date("假日 (週日) 官方表定班表驗測", datetime.datetime(2026, 11, 22, 9, 0))
print("\n" + "=" * 75)
