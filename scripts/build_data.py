import pandas as pd
import json
import re
from collections import Counter

EVENTS_CSV = 'data/立命館大学支部14期_OC_イベントリスト - 閲覧用_最新版 (3).csv'
CV_CSV = 'data/立命館大学支部14期_OCインフラ - エンターごとCV確認_累計.csv'
OUTPUT_JSON = 'data.json'

def merge_genres(series):
    items = set()
    for val in series.dropna():
        for g in str(val).split(','):
            g_clean = g.strip()
            if g_clean and g_clean != '-':
                g_clean = g_clean.replace('(', '（').replace(')', '）')
                items.add(g_clean)
    return sorted(items)

def merge_needs(series):
    items = []
    for val in series.dropna():
        s = str(val).strip()
        if s and s != '-' and s not in items:
            items.append(s)
    return ' / '.join(items)

def merge_dates(df_sub):
    dates = []
    end_col = [c for c in df_sub.columns if '終了時刻' in c]
    for _, r in df_sub.iterrows():
        d = str(r['開催日程']).strip() if pd.notna(r['開催日程']) else ''
        end_t = str(r[end_col[0]]).strip() if end_col and pd.notna(r[end_col[0]]) else ''
        if d:
            end_clean = re.sub(r'^[〜～\s]+', '', end_t)
            label = f"{d}〜{end_clean}" if end_clean and end_clean != 'nan' else d
            if label not in dates:
                dates.append(label)
    return dates

def main():
    df_events = pd.read_csv(EVENTS_CSV, skiprows=1)
    df_cv_raw = pd.read_csv(CV_CSV, header=None)

    df_users = df_cv_raw.iloc[7:].copy()
    df_users_clean = df_users[~df_users[2].astype(str).str.contains('テスト', na=False)].copy()

    # 1. 延べCV数（全セルカウント）と 2. ユニーク申込人数（学生ごとの重複除外カウント）を同時集計
    total_cv_counter = Counter()
    unique_user_counter = Counter()

    for _, row in df_users_clean.iterrows():
        raw_vals = [
            re.sub(r'\s+', ' ', str(v).strip())
            for v in row.iloc[4:].dropna()
            if str(v).strip() != ''
        ]
        total_cv_counter.update(raw_vals)
        unique_user_counter.update(set(raw_vals))

    df_events['event_norm'] = df_events['イベント'].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)

    records = []
    for event_norm, grp in df_events.groupby('event_norm', sort=False):
        first = grp.iloc[0]
        genres = merge_genres(grp['ジャンル'])
        needs = merge_needs(grp['ニーズ'])
        dates = merge_dates(grp)
        cv_val = int(total_cv_counter.get(event_norm, 0))
        app_val = int(unique_user_counter.get(event_norm, 0))

        records.append({
            'id': str(first['ユニークキー']),
            'title': str(first['イベント']).strip(),
            'cv': cv_val,
            'applicants': app_val,
            'genres': genres,
            'needs': needs,
            'url': str(first['URL']).strip(),
            'dates': dates[:4],
            'totalDates': len(dates)
        })

    records.sort(key=lambda x: (-x['cv'], -x['applicants'], -x['totalDates'], x['id']))

    output_data = {
        'totalStudents': len(df_users_clean),
        'totalEvents': len(records),
        'events': records
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, separators=(',', ':'))

    print(f"✅ 完了: {len(records)}件のデータを出力しました（延べCV・ユニーク申込人数対応）")

if __name__ == '__main__':
    main()
    