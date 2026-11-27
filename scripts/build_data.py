import pandas as pd
import json
import re
import os

# CSVファイルのパス（dataフォルダ内に配置した場合）
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
    for _, r in df_sub.iterrows():
        d = str(r['開催日程']).strip() if pd.notna(r['開催日程']) else ''
        # 改行コードの違い(\r\n / \n)を吸収して終了時刻列を取得
        end_col = [c for c in df_sub.columns if '終了時刻' in c]
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

    # テストアカウント除外
    df_users = df_cv_raw.iloc[7:].copy()
    df_users_clean = df_users[~df_users[2].astype(str).str.contains('テスト', na=False)].copy()

    # CV数の集計
    cv_series = df_users_clean.iloc[:, 4:].stack().dropna()
    cv_series_norm = cv_series.astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    cv_counts = cv_series_norm.value_counts().to_dict()

    df_events['event_norm'] = df_events['イベント'].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    df_events['cv_count'] = df_events['event_norm'].map(cv_counts).fillna(0).astype(int)

    records = []
    for event_norm, grp in df_events.groupby('event_norm', sort=False):
        first = grp.iloc[0]
        genres = merge_genres(grp['ジャンル'])
        needs = merge_needs(grp['ニーズ'])
        dates = merge_dates(grp)
        records.append({
            'id': str(first['ユニークキー']),
            'title': str(first['イベント']).strip(),
            'cv': int(first['cv_count']),
            'genres': genres,
            'needs': needs,
            'url': str(first['URL']).strip(),
            'dates': dates[:4],
            'totalDates': len(dates)
        })

    # CV数降順 → 日程数降順 → ID昇順でソート
    records.sort(key=lambda x: (-x['cv'], -x['totalDates'], x['id']))

    output_data = {
        'totalStudents': len(df_users_clean),
        'totalEvents': len(records),
        'events': records
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, separators=(',', ':'))

    print(f"✅ 完了: {len(records)}件のイベントデータを {OUTPUT_JSON} に出力しました！")

if __name__ == '__main__':
    main()
    