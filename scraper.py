import asyncio
import pandas as pd
from playwright.async_api import async_playwright

CITIES = {
    "Guntur": [
        "Guntur", "Tenali", "Narasaraopet", "Bapatla", "Chirala", "Mangalagiri",
        "Tadepalle", "Ponnur", "Repalle", "Sattenapalle", "Piduguralla", "Vinukonda",
        "Macherla", "Gurazala", "Amaravati", "Chilakaluripet", "Prathipadu",
        "Phirangipuram", "Karlapalem", "Nizampatnam", "Vemuru", "Kolluru",
        "Tsunduru", "Bhattiprolu", "Dachepalle", "Durgi", "Edlapadu", "Kakumanu",
        "Krosuru", "Medikonduru", "Morampudi", "Muppalla", "Nadendla",
        "Nakarikallu", "Nuzendla", "Palnad", "Pedakurapadu",
        "Rentachintala", "Rompicherla", "Tadikonda", "Thullur", "Veldurthi"
    ],
    "Krishna": [
        "Vijayawada", "Machilipatnam", "Gudivada", "Jaggaiahpet", "Nuzvid",
        "Kaikaluru", "Gannavaram", "Tiruvuru", "Mylavaram", "Nandigama",
        "Pamarru", "Vissannapeta", "Bapulapadu", "Avanigadda",
        "Koduru", "Movva", "Vuyyuru", "Bantumilli", "Challapalli", "Gampalagudem",
        "Ghantasala", "Guduru", "Hanuman Junction", "Ibrahimpatnam", "Kankipadu",
        "Mandavalli", "Musunuru", "Nagayalanka",
        "Pamidimukkala", "Penamaluru", "Pedana", "Reddigudem", "Unguturu",
        "Vatsavai", "Nandivada", "Mopidevi", "Kruthivennu",
        "Thotlavalluru", "Kondapalli"
    ],
    "Nellore": [
        "Nellore", "Kavali", "Gudur", "Sullurpeta", "Atmakur", "Naidupeta",
        "Alluru", "Sangam", "Venkatagiri", "Kovur", "Kaluvoya", "Podalakur",
        "Rapur", "Sydapuram", "Sriharikota", "Tada", "Buchireddipalem",
        "Dagadarthi", "Dakkili", "Duttaluru", "Indukurpet",
        "Jaladanki", "Kandukur", "Kota", "Manubolu", "Marripadu",
        "Muthukuru", "Ojili", "Padugupadu", "Pellakuru",
        "Penchalakona", "Ramachandrapuram", "Tangutur", "Udayagiri",
        "Vinjamur", "Bogole", "Ananthasagaram", "Balayapalle",
        "Bitragunta", "Chillakur"
    ],
    "Prakasam": [
        "Ongole", "Chirala", "Markapur", "Kandukur", "Giddalur", "Kanigiri",
        "Podili", "Darsi", "Addanki", "Chimakurthy", "Inkollu", "Santhamagaluru",
        "Pamuru", "Cumbum", "Tarlupadu", "Naguluppalapadu", "Mundlamuru",
        "Vetapalem", "Singarayakonda", "Korisapadu", "Maddipadu", "Parchur",
        "Santhanuthalapadu", "Tripuranthakam", "Yerragondapalem", "Zarugumalli",
        "Donakonda", "Kurichedu", "Martur", "Pedacherlo", "Tangutur",
        "Bestavaripeta", "Chandrasekharapuram", "Dornala", "Hanumanthuni Padu",
        "Kondapi", "Pullalacheruvu", "Racherla", "Ulavapadu", "Voletivaripalem"
    ],
    "East Godavari": [
        "Rajahmundry", "Kakinada", "Amalapuram", "Ramachandrapuram", "Peddapuram",
        "Samalkot", "Tuni", "Mandapeta", "Prathipadu", "Gollaprolu",
        "Alamuru", "Ambajipeta", "Anaparthy", "Biccavolu", "Draksharamam",
        "Gandepalle", "Gannavaram", "Gokavaram", "Jagannaikpur", "Jagannadhapuram",
        "Kothapeta", "Kovvur", "Malkipuram", "Mamidikuduru", "Maredumilli",
        "Nidadavole", "Palakollu", "Palakoderu", "Pithapuram", "Razole",
        "Ravulapalem", "Razam", "Rowthulapudi", "Sakhinetipalle", "Tallarevu",
        "Thondangi", "Turangi", "Undi", "Yelamanchili", "Yeleswaram",
        "Korukonda", "Allavaram", "Kadiam", "Annavaram", "Dommeru"
    ]
}

TOP_N = 20         # restaurants kept per list per town
MIN_RATING = 4.0   # "Most Popular" list only includes places rated at least this
TABS = 4           # restaurant pages opened in parallel (higher risks Google blocking)

# A place counts as a food spot if its Google category or name contains one of these
FOOD_WORDS = [
    "restaurant", "cafe", "café", "hotel", "dhaba", "biryani", "tiffin", "canteen",
    "bakery", "food", "mess", "ice cream", "sweet", "snack", "juice", "coffee",
    "tea", "takeaway", "take away", "eatery", "pizza", "burger", "bar", "grill",
    "kitchen", "dessert", "chaat", "caterer", "meal", "diner", "bistro", "buffet",
    "sandwich", "candy", "bhojanam", "bhavan", "tiffins", "foods",
]


async def collect_place_urls(page, city, district):
    """Go to search results and collect all place URLs."""
    query = f"restaurants in {city} {district} district Andhra Pradesh"
    url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    await page.goto(url, timeout=40000)
    await page.wait_for_timeout(3500)

    # Scroll results panel until Google shows the end-of-list marker
    for _ in range(40):
        try:
            panel = await page.query_selector('div[role="feed"]')
            if panel:
                await panel.evaluate("el => el.scrollBy(0, 2000)")
            else:
                await page.keyboard.press("End")
        except Exception:
            pass
        await page.wait_for_timeout(1200)
        if await page.query_selector('span.HlvSq'):
            break

    # Collect all hrefs
    cards = await page.query_selector_all('a[href*="/maps/place/"]')
    urls = []
    names = []
    seen = set()
    for card in cards:
        href = await card.get_attribute("href")
        if href and href not in seen:
            seen.add(href)
            # Try to get name from card
            name = ""
            for sel in ['div.fontHeadlineSmall', 'div[class*="fontHeadline"]']:
                el = await card.query_selector(sel)
                if el:
                    name = (await el.inner_text()).strip()
                    break
            if not name:
                name = (await card.get_attribute("aria-label") or "").strip()
            urls.append(href)
            names.append(name)

    return urls, names


async def get_details(page, url):
    """Open a place page and extract name, category, address, phone, rating and review count."""
    d = {"name": "", "category": "", "address": "", "phone": "",
         "rating": None, "reviews": 0, "url": url}
    try:
        await page.goto(url, timeout=30000)
        await page.wait_for_selector('h1.DUwDvf', timeout=10000)
        await page.wait_for_timeout(500)  # let the info rows finish rendering
        d["url"] = page.url

        async def text(sel):
            el = await page.query_selector(sel)
            return (await el.inner_text()).strip() if el else ""

        d["name"] = await text('h1.DUwDvf')
        d["category"] = await text('button[jsaction*="category"]')
        d["address"] = await text('button[data-item-id="address"] .Io6YTe')
        d["phone"] = await text('button[data-item-id^="phone"] .Io6YTe')

        try:
            d["rating"] = float(await text('div.F7nice span[aria-hidden="true"]'))
        except ValueError:
            pass

        reviews_el = await page.query_selector('div.F7nice span[aria-label$="reviews"], div.F7nice span[aria-label$="review"]')
        if reviews_el:
            digits = "".join(c for c in (await reviews_el.get_attribute("aria-label")) if c.isdigit())
            d["reviews"] = int(digits) if digits else 0
    except Exception as e:
        print(f"    detail error: {e}", flush=True)

    return d


def is_food_place(category, name):
    if not category:
        return True  # no category shown; give it the benefit of the doubt
    text = f"{category} {name}".lower()
    return any(w in text for w in FOOD_WORDS)


async def search_city(context, city, district):
    """Returns {"Top Rated": [...], "Most Popular": [...]} for one town."""
    results = []
    try:
        search_page = await context.new_page()
        urls, names = await collect_place_urls(search_page, city, district)
        await search_page.close()
        print(f"  [{city}] {len(urls)} places to visit", flush=True)

        queue = asyncio.Queue()
        for i, item in enumerate(zip(urls, names)):
            queue.put_nowait((i, item))

        async def worker():
            page = await context.new_page()
            while not queue.empty():
                i, (url, list_name) = queue.get_nowait()
                d = await get_details(page, url)
                name = d["name"] or list_name
                if not name:
                    continue
                food = is_food_place(d["category"], name)
                results.append({
                    "District": district,
                    "City/Town": city,
                    "Restaurant Name": name,
                    "Category": d["category"],
                    "Address": d["address"],
                    "Phone": d["phone"],
                    "Rating": d["rating"],
                    "Reviews": d["reviews"],
                    "Google Maps Link": d["url"],
                    "_food": food,
                })
                print(f"    [{i+1}] {name} | {d['category'] or '?'} | {d['rating']} ({d['reviews']} reviews)"
                      f"{'' if food else ' | SKIPPED: not food'}", flush=True)
            await page.close()

        await asyncio.gather(*(worker() for _ in range(TABS)))

    except Exception as e:
        print(f"  ERROR [{city}]: {e}", flush=True)

    food = [r for r in results if r.pop("_food")]
    add_popularity_scores(food)

    top_rated = sorted(food, key=lambda r: r["Score"], reverse=True)[:TOP_N]
    popular = sorted((r for r in food if (r["Rating"] or 0) >= MIN_RATING),
                     key=lambda r: r["Reviews"], reverse=True)[:TOP_N]
    return {"Top Rated": top_rated, "Most Popular": popular}


def add_popularity_scores(results):
    """Bayesian average (IMDb-style weighted rating), computed per town:
    score = v/(v+m) * R + m/(v+m) * C
    R = place rating, v = its review count, C = mean rating in town,
    m = median review count in town (how many reviews before R dominates)."""
    rated = [r for r in results if r["Rating"] is not None and r["Reviews"] > 0]
    if not rated:
        for r in results:
            r["Score"] = 0.0
        return
    C = sum(r["Rating"] for r in rated) / len(rated)
    counts = sorted(r["Reviews"] for r in rated)
    m = max(counts[len(counts) // 2], 1)
    for r in results:
        v, R = r["Reviews"], r["Rating"]
        r["Score"] = round(v / (v + m) * R + m / (v + m) * C, 3) if R is not None else 0.0


def save_to_excel(lists, output):
    """lists = {"Top Rated": [rows], "Most Popular": [rows]}; one sheet per list."""
    sort_key = {"Top Rated": "Score", "Most Popular": "Reviews"}
    counts = {}
    with pd.ExcelWriter(output) as writer:
        for sheet, rows in lists.items():
            df = pd.DataFrame(rows)
            if not df.empty:
                df.drop_duplicates(subset=["Restaurant Name", "City/Town", "District"], inplace=True)
                df.sort_values(["District", "City/Town", sort_key[sheet]],
                               ascending=[True, True, False], kind="stable", inplace=True)
                df.insert(0, "Rank", df.groupby(["District", "City/Town"]).cumcount() + 1)
            df.to_excel(writer, sheet_name=sheet, index=False)
            counts[sheet] = len(df)
    return counts


async def main():
    lists = {"Top Rated": [], "Most Popular": []}
    OUTPUT = "restaurants_AP.xlsx"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )

        total_cities = sum(len(v) for v in CITIES.values())
        done = 0

        for district, cities in CITIES.items():
            print(f"\n{'='*50}", flush=True)
            print(f"DISTRICT: {district}", flush=True)
            print(f"{'='*50}", flush=True)
            for city in cities:
                done += 1
                print(f"\n[{done}/{total_cities}] Searching: {city}, {district}", flush=True)
                town = await search_city(context, city, district)
                for name, rows in town.items():
                    lists[name].extend(rows)

                # Save to Excel after EVERY city
                counts = save_to_excel(lists, OUTPUT)
                print(f"  -> Total in Excel: {counts}", flush=True)

                await asyncio.sleep(2)

        await browser.close()

    print(f"\n{'='*50}", flush=True)
    print(f"DONE! Excel saved to {OUTPUT}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
