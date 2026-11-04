# Khayal Shopify theme

The new Khayal design as a full Shopify theme. Your products, prices, cart, checkout and customer accounts keep working.

- `khayal-theme/`: theme source
- `khayal-theme.zip`: ready to upload

## Install (your current theme stays untouched)

1. Shopify admin → **Online Store → Themes**.
2. **Add theme → Upload zip file** → choose `khayal-theme.zip`.
3. On the new "Khayal" theme, click **Customize** to preview it with your real products.
4. When it looks right, click **Publish**. You can switch back to the old theme at any time.

## Fill in before publishing (Customize → click each section)

- **Khayal tack room**: tiles and chips already link to your real collections (saddles, bridles, halters, accessories, martingales, safety, saddle-pads, grooming, feed-bags, hay-nets, stirrups, tendon-boots). Upload sharper photos if you have them.
- **Khayal rides & training**: add prices (e.g. `LE 1,500`). Prices stay hidden while empty. Buttons go to `/pages/endurance`, because the Khayal Rides and Training collections are empty.
- **Khayal numbers / hero badge**: confirm or edit 70+ products (the store has 76), 60K+, 4 locations, 30%.
- **Khayal story**: add the Shark Tank story text and the episode link. The play button appears once a link is set.
- **Khayal reviews**: add real customer reviews. The section stays hidden until you add one.
- **Footer**: phone, WhatsApp, email, App Store / Google Play links. Each item stays hidden while empty.
- **Theme settings → Social media**: TikTok and Facebook links. Instagram is preset to @kha_y_all.
- **Header**: optionally pick a menu. Otherwise it shows Shop, Rides, Training, Endurance, Contact.
- Your `/pages/contact` page: in the page editor, set its template to `page.contact` to get the new contact form.

## Product data

`khayal-products.csv` lists all 76 products (101 variants) from khayalhorses.com, with prices, availability and links.

## Ride & endurance booking

Customers pick a date, time, distance and number of riders, enter their details, and pay at normal Shopify checkout. Every booking shows up in **Orders** with the date, time, rider name, WhatsApp number and level.

One-time setup (about 5 minutes):

1. **Products → Add product**: title **`Pyramids Ride`**. Set the price per rider. Under **Inventory**, untick "Track quantity" (or set it to the number of seats you have). Untick **"This is a physical product"** so no shipping is charged. Add photos. On the right, set **Theme template → `ride`**. Add it to the **Khayal Rides** collection. Save.
2. Do the same with title **`Endurance Training`**, template **`endurance`**. Optional: add an option **Distance** with values `7 km` and `20 km` and different prices.
3. Check that the product URLs are `/products/pyramids-ride` and `/products/endurance-training` (they are, if the titles match). The homepage cards, menu and footer already link there.
4. On your Endurance page, change the "Register Now" link to `/products/endurance-training`.
5. In **Customize → Products → Pyramids Ride / Endurance Training** you can change days, time slots, closed dates, the booking cutoff, max riders and rider levels.

Note: Shopify does not limit seats per date. To close a full date, add it under "Closed dates" in the booking section.
