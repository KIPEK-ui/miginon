from django.db import migrations

# General agro-ecological zone guidance, not a county-specific agronomic
# survey - Kenya's 47 counties cluster into a handful of well-known zones,
# so this authors crop suitability per zone and expands each zone's crop
# list across every county assigned to it (rather than 47 bespoke entries).
# Farmers should still confirm locally (soil type, microclimate and altitude
# vary within a county) with their county agricultural extension office.

ZONE_COUNTIES = {
    'Central Highlands': [
        'Kiambu', 'Kirinyaga', "Murang'a", 'Nyeri', 'Nyandarua', 'Embu', 'Meru', 'Tharaka-Nithi',
    ],
    'Rift Valley Highlands': [
        'Nakuru', 'Uasin Gishu', 'Trans Nzoia', 'Nandi', 'Kericho', 'Bomet',
        'Elgeyo-Marakwet', 'Baringo', 'Laikipia', 'Narok',
    ],
    'Lake Victoria Basin / Western': [
        'Kakamega', 'Bungoma', 'Busia', 'Vihiga', 'Siaya', 'Kisumu', 'Homa Bay', 'Migori', 'Kisii', 'Nyamira',
    ],
    'Coastal': [
        'Mombasa', 'Kilifi', 'Kwale', 'Lamu', 'Tana River', 'Taita-Taveta',
    ],
    'Eastern semi-arid': [
        'Machakos', 'Makueni', 'Kitui',
    ],
    'Arid / ASAL': [
        'Turkana', 'Marsabit', 'Wajir', 'Mandera', 'Garissa', 'Isiolo', 'Samburu', 'Kajiado', 'West Pokot',
    ],
    'Nairobi & environs': [
        'Nairobi',
    ],
}

# (crop_name, notes, planting_season) per zone - 4-5 crops each.
ZONE_CROPS = {
    'Central Highlands': [
        ('Tea', 'Cool highland climate and well-drained volcanic soils suit tea bushes well.',
         'Year-round; main harvest flushes March-June and Oct-Dec'),
        ('Coffee (Arabica)', 'Altitude and rich volcanic soils favor high-quality Arabica coffee.',
         'March-May or Oct-Nov, with the rains'),
        ('Irish potatoes', 'Cool temperatures and altitude favor potato production.',
         'March-April long rains, or Sept-Oct short rains'),
        ('Napier grass (dairy fodder)', "Reliable rainfall supports year-round fodder for the region's dairy herds.",
         'Start of either rainy season'),
        ('French beans', 'Cool climate and proximity to export markets support high-value horticulture.',
         'Year-round with irrigation, or timed to the rains'),
    ],
    'Rift Valley Highlands': [
        ('Wheat', "Cool climate and open highland plains make this Kenya's main wheat belt.",
         'March-April long rains, harvested Aug-Sept'),
        ('Maize', 'Fertile highland soils and moderate rainfall support high-yield maize.',
         'March-April long rains'),
        ('Tea', "Kericho and Bomet are among Kenya's principal tea-growing highlands.",
         'Year-round with rain'),
        ('Napier / Rhodes grass (fodder)', "Cool climate grassland supports the region's dairy and beef herds.",
         'Start of the rains'),
        ('Pyrethrum', "High-altitude, cool climate historically suited Kenya's pyrethrum belt.",
         'Seedlings planted at the start of the rains'),
    ],
    'Lake Victoria Basin / Western': [
        ('Sugarcane', 'Warm, humid climate and reliable rainfall around the lake basin suit sugarcane.',
         'Planted year-round; 18-24 month maturity'),
        ('Maize', "A staple crop across the region's fertile, well-watered soils.",
         'March-April long rains, or Aug-Sept short rains'),
        ('Sorghum', 'Tolerant of the more variable rainfall further from the lakeshore.',
         'March-April'),
        ('Groundnuts', 'Sandy loam soils in the basin suit groundnut production.',
         'March-April'),
        ('Cotton', 'A traditional cash crop across parts of Busia, Bungoma and Siaya.',
         'March-May'),
    ],
    'Coastal': [
        ('Coconut', 'Sandy coastal soils and humid climate are ideal for coconut palms.',
         'Planted year-round; matures in 5-7 years'),
        ('Cashew nut', 'Well-drained coastal soils suit cashew trees, a major Kwale/Kilifi cash crop.',
         'Start of the rains, March-May'),
        ('Mango', "Warm coastal climate supports Kenya's main mango-growing region.",
         'March-May or Oct-Dec'),
        ('Cassava', 'Drought-tolerant and well-suited to coastal sandy soils.',
         'Year-round with adequate moisture'),
        ('Sesame (simsim)', 'A traditional, drought-tolerant coastal cash crop.',
         'April-June'),
    ],
    'Eastern semi-arid': [
        ('Sorghum', "Drought-tolerant and well-suited to the region's lower, more variable rainfall.",
         'October-December short rains'),
        ('Pearl millet', 'Thrives where maize often fails due to low or unreliable rainfall.',
         'October-December'),
        ('Green grams (ndengu)', 'A reliable, drought-tolerant legume cash crop for this region.',
         'October-December short rains'),
        ('Cowpeas', 'Drought-hardy and improves soil fertility.',
         'October-December'),
        ('Mango', 'Makueni in particular is a major mango-growing county.',
         'Planted at the start of the rains'),
    ],
    'Arid / ASAL': [
        ('Sorghum', "One of the few cereals reliable enough for the region's low, erratic rainfall.",
         'With the onset of rains (timing varies locally)'),
        ('Pearl millet', 'Highly drought-tolerant, a traditional ASAL staple.',
         'With the onset of rains'),
        ('Cowpeas', 'Drought-tolerant legume commonly intercropped with cereals here.',
         'With the onset of rains'),
        ('Drought-tolerant fodder grasses', "Supports the region's predominantly livestock-based economy.",
         'With the onset of rains'),
    ],
    'Nairobi & environs': [
        ('Sukuma wiki (kale)', 'Strong urban market demand supports intensive peri-urban vegetable growing.',
         'Year-round with irrigation'),
        ('Spinach', "Fast-growing, high-value crop for Nairobi's urban and peri-urban farmers.",
         'Year-round with irrigation'),
        ('Tomatoes', 'Strong urban market demand supports greenhouse and open-field production.',
         'Year-round with irrigation, avoiding the heaviest rains'),
        ('Napier grass (dairy fodder)', 'Supports the many small-scale zero-grazing dairy units around the city.',
         'Start of the rains, or year-round with irrigation'),
    ],
}


def seed_crop_suitability(apps, schema_editor):
    CropSuitability = apps.get_model('advisory', 'CropSuitability')
    rows = [
        CropSuitability(county=county, zone=zone, crop_name=crop_name, notes=notes, planting_season=planting_season)
        for zone, counties in ZONE_COUNTIES.items()
        for crop_name, notes, planting_season in ZONE_CROPS[zone]
        for county in counties
    ]
    CropSuitability.objects.bulk_create(rows)


def unseed_crop_suitability(apps, schema_editor):
    apps.get_model('advisory', 'CropSuitability').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('advisory', '0003_cropsuitability'),
    ]

    operations = [
        migrations.RunPython(seed_crop_suitability, unseed_crop_suitability),
    ]
