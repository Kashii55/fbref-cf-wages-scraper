import time
import csv
import re
import os
import random
from DrissionPage import ChromiumPage
from CloudflareBypasser import CloudflareBypasser

# ─── CONFIG ───────────────────────────────────────────────────────────────────
OUTPUT_FILE = "wages_data.csv"
DELAY_BETWEEN_PAGES = (3, 6)
DELAY_BETWEEN_TEAMS = (4, 8)
MAX_TEAMS_PER_SEASON = 20

LEAGUES = {
    "Premier League": {
        "comp_id": 9,
        "slug": "Premier-League",
        "start_season": 2013,
        "end_season": 2025,
    },
    "Bundesliga": {
        "comp_id": 20,
        "slug": "Bundesliga",
        "start_season": 2013,
        "end_season": 2025,
    },
    "La Liga": {
        "comp_id": 12,
        "slug": "La-Liga",
        "start_season": 2013,
        "end_season": 2025,
    },
    "Ligue 1": {
        "comp_id": 13,
        "slug": "Ligue-1",
        "start_season": 2013,
        "end_season": 2025,
    },
    "Serie A": {
        "comp_id": 11,
        "slug": "Serie-A",
        "start_season": 2009,
        "end_season": 2025,
    },
}

FIELDNAMES = [
    "Season", "League", "Team",
    "Player", "Player link", "Player ID",
    "Nation", "Position", "Age",
    "Weekly Wage (£)", "Weekly Wage (€)", "Weekly Wage ($)",
    "Annual Wage (£)", "Annual Wage (€)", "Annual Wage ($)",
    "Notes",
]

BASE = "https://fbref.com"

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def season_label(start_year: int) -> str:
    return f"{start_year}-{start_year + 1}"

def season_display(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"

def league_wages_url(comp_id: int, slug: str, start_year: int) -> str:
    if start_year == 2025:
        return f"{BASE}/en/comps/{comp_id}/wages/{slug}-Wages"
    s = season_label(start_year)
    return f"{BASE}/en/comps/{comp_id}/{s}/wages/{s}-{slug}-Wages"

def safe_get(driver: ChromiumPage, url: str, cf: CloudflareBypasser) -> bool:
    try:
        driver.get(url)
        cf.bypass()
        time.sleep(random.uniform(*DELAY_BETWEEN_PAGES))
        return True
    except Exception as e:
        print(f"  [ERROR] safe_get({url}): {e}")
        return False

def parse_wage_cell(cell_html: str, cell_text: str):
    if not cell_html and not cell_text:
        return "", "", ""

    src = cell_html if cell_html else cell_text

    gbp_match = re.search(r"(?:£|&pound;|Â£)\s*([\d,]+)", src, re.IGNORECASE)
    gbp = gbp_match.group(1).replace(",", "") if gbp_match else ""

    eur_match = re.search(r"(?:€|&euro;|â‚¬)\s*([\d,]+)", src, re.IGNORECASE)
    eur = eur_match.group(1).replace(",", "") if eur_match else ""

    usd_match = re.search(r"\$([\d,]+)", src)
    usd = usd_match.group(1).replace(",", "") if usd_match else ""

    if not gbp and cell_text:
        m = re.search(r"(?:£|&pound;|Â£)\s*([\d,]+)", cell_text, re.IGNORECASE)
        gbp = m.group(1).replace(",", "") if m else ""

    if not eur and cell_text:
        m = re.search(r"(?:€|&euro;|â‚¬)\s*([\d,]+)", cell_text, re.IGNORECASE)
        eur = m.group(1).replace(",", "") if m else ""

    return gbp, eur, usd

# ─── TEAM DISCOVERY ───────────────────────────────────────────────────────────
def get_teams(driver: ChromiumPage, cf: CloudflareBypasser,
              league_url: str) -> list[dict]:
    print(f"  [League page] {league_url}")
    if not safe_get(driver, league_url, cf):
        return []

    teams = []

    try:
        anchors = driver.eles("css:#squad_wages .left a")
        for a in anchors:
            href = a.attr("href") or ""
            name = a.text.strip()
            if "/squads/" in href and name:
                full_url = BASE + href if href.startswith("/") else href
                teams.append({"name": name, "url": full_url})
        if teams:
            print(f"    [selector 1 hit] #squad_wages .left a → {len(teams)} raw links")
    except Exception as e:
        print(f"    [selector 1 error] {e}")

    if not teams:
        try:
            anchors = driver.eles("css:.force_mobilize th + .left a")
            for a in anchors:
                href = a.attr("href") or ""
                name = a.text.strip()
                if "/squads/" in href and name:
                    full_url = BASE + href if href.startswith("/") else href
                    teams.append({"name": name, "url": full_url})
            if teams:
                print(f"    [selector 2 hit] → {len(teams)} raw links")
            else:
                print("    [WARN] Both selectors returned 0 squad links")
        except Exception as e:
            print(f"    [selector 2 error] {e}")

    seen = set()
    unique = []
    for t in teams:
        if t["url"] not in seen:
            seen.add(t["url"])
            unique.append(t)
            if len(unique) >= MAX_TEAMS_PER_SEASON:
                break

    print(f"    → {len(unique)} unique teams (cap={MAX_TEAMS_PER_SEASON})")
    return unique

# ─── PLAYER SCRAPING ──────────────────────────────────────────────────────────
def scrape_team_wages(driver: ChromiumPage, cf: CloudflareBypasser,
                      team: dict, season: str, league: str) -> list[dict]:
    print(f"    [Team] {team['name']}  →  {team['url']}")
    if not safe_get(driver, team["url"], cf):
        return []

    records = []
    try:
        # Grab ALL tr rows (not just tbody) so we can filter the interspersed
        # header-repeat rows that fbref inserts every ~10 rows
        table_rows = driver.eles("css:#wages tr")

        for row in table_rows:
            try:
                # ── Skip mid-table repeated header rows ───────────────────────
                row_class = row.attr("class") or ""
                if "thead" in row_class:
                    continue

                # Skip <th scope="col"> column-header rows
                if row.ele("css:th[data-stat='player'][scope='col']"):
                    continue

                # ── Player ────────────────────────────────────────────────────
                player_th = row.ele("css:th[data-stat='player']")
                if not player_th:
                    continue

                player_a    = player_th.ele("tag:a")
                player_name = player_a.text.strip() if player_a else player_th.text.strip()
                player_href = player_a.attr("href") if player_a else ""
                player_link = (BASE + player_href
                               if player_href and player_href.startswith("/")
                               else player_href)

                player_id = ""
                if player_link:
                    m = re.search(r"/players/([a-f0-9]+)/", player_link)
                    player_id = m.group(1) if m else ""
                if not player_id and player_th:
                    player_id = player_th.attr("data-append-csv") or ""

                # ── Nation ────────────────────────────────────────────────────
                nation_td = row.ele("css:td[data-stat='nationality']")
                nation = ""
                if nation_td:
                    nation_a = nation_td.ele("tag:a")
                    if nation_a:
                        nation = nation_a.text.strip()

                # ── Position ──────────────────────────────────────────────────
                pos_td   = row.ele("css:td[data-stat='position']")
                position = pos_td.text.strip() if pos_td else ""

                # ── Age ───────────────────────────────────────────────────────
                age_td = row.ele("css:td[data-stat='age']")
                age    = age_td.text.strip() if age_td else ""

                # ── Weekly wages ──────────────────────────────────────────────
                weekly_td   = row.ele("css:td[data-stat='weekly_wages']")
                # KEY FIX: use inner_html (not .text) to preserve £ and €
                weekly_html = weekly_td.inner_html.strip() if weekly_td else ""
                weekly_text = weekly_td.text.strip()       if weekly_td else ""
                wk_gbp, wk_eur, wk_usd = parse_wage_cell(weekly_html, weekly_text)

                # ── Annual wages ──────────────────────────────────────────────
                annual_td   = row.ele("css:td[data-stat='annual_wages']")
                # KEY FIX: use inner_html (not .text) to preserve £ and €
                annual_html = annual_td.inner_html.strip() if annual_td else ""
                annual_text = annual_td.text.strip()       if annual_td else ""
                an_gbp, an_eur, an_usd = parse_wage_cell(annual_html, annual_text)

                # ── Notes ─────────────────────────────────────────────────────
                notes_td = row.ele("css:td[data-stat='notes']")
                notes    = notes_td.text.strip() if notes_td else ""

                if not player_name:
                    continue

                records.append({
                    "Season":           season,
                    "League":           league,
                    "Team":             team["name"],
                    "Player":           player_name,
                    "Player link":      player_link,
                    "Player ID":        player_id,
                    "Nation":           nation,
                    "Position":         position,
                    "Age":              age,
                    "Weekly Wage (£)":  wk_gbp,
                    "Weekly Wage (€)":  wk_eur,
                    "Weekly Wage ($)":  wk_usd,
                    "Annual Wage (£)":  an_gbp,
                    "Annual Wage (€)":  an_eur,
                    "Annual Wage ($)":  an_usd,
                    "Notes":            notes,
                })
            except Exception as row_err:
                print(f"      [WARN] Row parse error: {row_err}")

    except Exception as e:
        print(f"    [ERROR] scrape_team_wages: {e}")

    print(f"      → {len(records)} players scraped")
    return records

# ─── RESUME / PROGRESS HELPERS ────────────────────────────────────────────────
def load_done_keys(filepath: str) -> set:
    done = set()
    if not os.path.exists(filepath):
        return done
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            done.add((row["Season"], row["League"], row["Team"]))
    return done

def append_rows(filepath: str, rows: list[dict], write_header: bool):
    mode = "w" if write_header else "a"
    # utf-8-sig = UTF-8 with BOM → Excel reads £/€/accented names correctly
    with open(filepath, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    driver = ChromiumPage()
    cf     = CloudflareBypasser(driver, max_retries=5)

    done_keys    = load_done_keys(OUTPUT_FILE)
    write_header = not os.path.exists(OUTPUT_FILE)

    try:
        for league_name, info in LEAGUES.items():
            comp_id = info["comp_id"]
            slug    = info["slug"]

            for start_year in range(info["start_season"], info["end_season"] + 1):
                season     = season_display(start_year)
                league_url = league_wages_url(comp_id, slug, start_year)

                print(f"\n{'='*60}")
                print(f"League: {league_name}  |  Season: {season}")
                print(f"URL:    {league_url}")
                print(f"{'='*60}")

                teams = get_teams(driver, cf, league_url)
                if not teams:
                    print("  No teams found – skipping season.")
                    continue

                for team in teams:
                    key = (season, league_name, team["name"])
                    if key in done_keys:
                        print(f"    [SKIP] Already scraped: {team['name']}")
                        continue

                    rows = scrape_team_wages(driver, cf, team, season, league_name)
                    if rows:
                        append_rows(OUTPUT_FILE, rows, write_header=write_header)
                        write_header = False
                        done_keys.add(key)

                    time.sleep(random.uniform(*DELAY_BETWEEN_TEAMS))

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted. Progress saved to", OUTPUT_FILE)
    finally:
        driver.quit()

    print(f"\n[DONE] Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()