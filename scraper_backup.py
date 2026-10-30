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


async def collect_place_urls(page, city, district):
    """Go to search results and collect all place URLs."""
    query = f"restaurants in {city} {district} district Andhra Pradesh"
    url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    await page.goto(url, timeout=40000)
    await page.wait_for_timeout(3500)

    # Scroll results panel to load more
    for _ in range(8):
        try:
            panel = await page.query_selector('div[role="feed"]')
            if panel:
                await panel.evaluate("el => el.scrollBy(0, 1200)")
            else:
                await page.keyboard.press("End")
        except Exception:
            pass
        await page.wait_for_timeout(1200)

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

    return urls[:20], names[:20]  # top 20


async def get_details(page, url):
    """Navigate to a place URL and extract address and phone."""
    address, phone, final_url = "", "", url
    try:
        await page.goto(url, timeout=30000)
        await page.wait_for_timeout(3000)
        final_url = page.url

        addr_el = await page.query_selector('button[data-item-id="address"] .Io6YTe')
        if addr_el:
            address = (await addr_el.inner_text()).strip()

        phone_el = await page.query_selector('button[data-item-id^="phone"] .Io6YTe')
        if phone_el:
            phone = (await phone_el.inner_text()).strip()
    except Exception as e:
        print(f"    detail error: {e}", flush=True)

    return address, phone, final_url


async def search_city(page, city, district):
    results = []
    try:
        urls, names = await collect_place_urls(page, city, district)
        print(f"  [{city}] {len(urls)} places to visit", flush=True)

        for i, (url, name) in enumerate(zip(urls, names)):
            try:
                address, phone, final_url = await get_details(page, url)

                # Get name from page title if not captured from list
                if not name:
                    title_el = await page.query_selector('h1.DUwDvf, h1[class*="fontHeadline"]')
                    if title_el:
                        name = (await title_el.inner_text()).strip()

                if name:
                    results.append({
                        "District": district,
                        "City/Town": city,
                        "Restaurant Name": name,
                        "Address": address,
                        "Phone": phone,
                        "Google Maps Link": final_url
                    })
                    print(f"    [{i+1}] {name} | {phone or 'no phone'}", flush=True)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"    [{i+1}] skip: {e}", flush=True)
                continue

    except Exception as e:
        print(f"  ERROR [{city}]: {e}", flush=True)

    return results


def save_to_excel(all_results, output):
    df = pd.DataFrame(all_results)
    df.drop_duplicates(subset=["Restaurant Name", "City/Town", "District"], inplace=True)
    df.sort_values(["District", "City/Town"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_excel(output, index=False)
    return len(df)


async def main():
    all_results = []
    OUTPUT = "restaurants_AP.xlsx"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        total_cities = sum(len(v) for v in CITIES.values())
        done = 0

        for district, cities in CITIES.items():
            print(f"\n{'='*50}", flush=True)
            print(f"DISTRICT: {district}", flush=True)
            print(f"{'='*50}", flush=True)
            for city in cities:
                done += 1
                print(f"\n[{done}/{total_cities}] Searching: {city}, {district}", flush=True)
                results = await search_city(page, city, district)
                all_results.extend(results)

                # Save to Excel after EVERY city
                count = save_to_excel(all_results, OUTPUT)
                print(f"  -> {len(results)} added | Total in Excel: {count}", flush=True)

                await asyncio.sleep(2)

        await browser.close()

    print(f"\n{'='*50}", flush=True)
    print(f"DONE! Excel saved to {OUTPUT}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
