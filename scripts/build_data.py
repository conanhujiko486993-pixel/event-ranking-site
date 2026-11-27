import pandas as pd
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

EVENTS_CSV = 'data/立命館大学支部14期_OC_イベントリスト - 閲覧用_最新版 (3).csv'
CV_CSV = 'data/立命館大学支部14期_OCインフラ - エンターごとCV確認_累計.csv'
OUTPUT_JSON = 'data.json'

GENERIC_BRACKET_WORDS = (
    '28卒', '27卒', 'web', '締切', '特典', 'アマギフ', '早期', '限定',
    '1day', '対面', 'オンライン', '個別', '選考', '説明会', '最終', '募集'
)
GENERIC_SUFFIXES = {
    '会社説明会', '説明会', '選考会', '座談会', 'インターンシップ',
    '1day仕事体験', '社員fb付き', '本選考'
}

def norm(s):
    s = unicodedata.normalize('NFKC', str(s).strip())
    return re.sub(r'\s+', ' ', s)

def strip_brackets_and_dates(s):
    s_clean = re.sub(r'【[^】]*】', ' ', s)
    s_clean = re.sub(r'\[[^\]]*\]', ' ', s_clean)
    s_clean = re.sub(r'《[^》]*》', ' ', s_clean)
    s_clean = re.sub(r'※[^※]*※', ' ', s_clean)
    return re.sub(r'\s+', ' ', s_clean).strip()

def extract_company_brackets(s):
    brackets = re.findall(r'【([^】]+)】', s)
    comps = []
    for b in brackets:
        b_low = b.lower()
        if not any(g in b_low for g in GENERIC_BRACKET_WORDS) and len(b.strip()) >= 3:
            comps.append(b.strip())
    return comps

def is_related_title(ev_norm, cv_norm):
    if ev_norm == cv_norm:
        return False

    ev_comps = extract_company_brackets(ev_norm)
    cv_comps = extract_company_brackets(cv_norm)
    if ev_comps and not any(c in cv_norm for c in ev_comps):
        return False
    if cv_comps and not any(c in ev_norm for c in cv_comps):
        return False

    ev_suffix = ev_norm.split('|')[-1].strip() if '|' in ev_norm else ''
    cv_suffix = cv_norm.split('|')[-1].strip() if '|' in cv_norm else ''
    suffix_match = (
        len(ev_suffix) >= 5 and len(cv_suffix) >= 5
        and ev_suffix.lower() not in GENERIC_SUFFIXES
        and cv_suffix.lower() not in GENERIC_SUFFIXES
        and (
            ev_suffix == cv_suffix
            or (len(ev_suffix) >= 8 and len(cv_suffix) >= 8 and (ev_suffix in cv_suffix or cv_suffix in ev_suffix))
        )
    )

    ev_core = strip_brackets_and_dates(ev_norm)
    cv_core = strip_brackets_and_dates(cv_norm)
    full_sim = SequenceMatcher(None, ev_norm, cv_norm).ratio()
    core_sim = SequenceMatcher(None, ev_core, cv_core).ratio() if (len(ev_core) >= 14 and len(cv_core) >= 14) else 0

    return suffix_match or full_sim >= 0.78 or core_sim >= 0.78

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

    # 学生ごとの申込履歴リスト（正規化済み）
    user_event_lists = []
    total_cv_counter = Counter()
    unique_user_counter = Counter()

    for _, row in df_users_clean.iterrows():
        raw_vals = [
            norm(v)
            for v in row.iloc[4:].dropna()
            if str(v).strip() != ''
        ]
        user_event_lists.append(raw_vals)
        total_cv_counter.update(raw_vals)
        unique_user_counter.update(set(raw_vals))

    all_cv_titles = list(total_cv_counter.keys())
    df_events['event_norm'] = df_events['イベント'].map(norm)

    records = []
    for event_norm, grp in df_events.groupby('event_norm', sort=False):
        first = grp.iloc[0]
        genres = merge_genres(grp['ジャンル'])
        needs = merge_needs(grp['ニーズ'])
        dates = merge_dates(grp)

        # 現行枠（完全一致）
        exact_cv = int(total_cv_counter.get(event_norm, 0))
        exact_app = int(unique_user_counter.get(event_norm, 0))

        # 旧枠・別タイトル（類似・同一企業）の探索
        related_titles = [t for t in all_cv_titles if is_related_title(event_norm, t)]
        related_titles.sort(key=lambda t: -total_cv_counter[t])

        past_cv = sum(int(total_cv_counter[t]) for t in related_titles)

        # 現行枠＋旧枠を合算した合計値（ユニーク人数は同一学生の重複も除外して正確にカウント）
        target_set = {event_norm} | set(related_titles)
        total_cv = exact_cv + past_cv
        total_app = sum(1 for u_list in user_event_lists if any(t in target_set for t in u_list))

        records.append({
            'id': str(first['ユニークキー']),
            'title': str(first['イベント']).strip(),
            'cv': total_cv,
            'applicants': total_app,
            'exactCv': exact_cv,
            'exactApplicants': exact_app,
            'pastCv': past_cv,
            'pastTitles': [
                {'title': t, 'cv': int(total_cv_counter[t])}
                for t in related_titles[:3]
            ],
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

    linked_count = sum(1 for r in records if r['pastCv'] > 0)
    print(f"✅ 完了: {len(records)}件出力（うち {linked_count}件に旧枠・別タイトル実績を合算しました）")

if __name__ == '__main__':
    main()
    