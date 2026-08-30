from django.db import migrations

# Sourced from KALRO's own directory (kalro.org/kps/centres.php, lis.kalro.org)
# via web research - coordinates are town-level estimates (KALRO does not
# publish exact facility GPS), not surveyed addresses. Entries KALRO's own
# site didn't clearly confirm were left out rather than guessed.
AGRI_CENTERS = [
    ('KALRO Headquarters', 'Nairobi', 'Loresho', -1.2477, 36.7830, 'Regional HQ / coordination', '+254 722 206986', 'info@kalro.org'),
    ('KALRO Dairy Research Institute - Naivasha', 'Nakuru', 'Naivasha', -0.7172, 36.4310, 'Dairy cattle research (HQ)', '', ''),
    ('KALRO Dairy Research Centre - Ol Joro Orok', 'Nyandarua', 'Ol Joro Orok', -0.3500, 36.5700, 'Dairy, highland seed/planting material (potato, maize, oats, Napier)', '', ''),
    ('KALRO Dairy Research Centre - Msabaha', 'Kilifi', 'Msabaha', -3.3667, 39.9667, 'Coastal dairy research', '', ''),
    ('KALRO Food Crops Research Institute - Njoro', 'Nakuru', 'Njoro', -0.3333, 35.9333, 'Cereals (wheat, barley), food crops', '051-61576', 'kalronjoro@kalronjoro.org'),
    ('KALRO Food Crops Research Institute - Kitale', 'Trans Nzoia', 'Kitale', 1.0157, 35.0062, 'Food crops HQ (maize, beans)', '', ''),
    ('KALRO Food Crops Research Institute (AMRI) - Katumani', 'Machakos', 'Katumani', -1.5827, 37.2634, 'Dryland crops & agricultural mechanization', '+254 710 906600', 'director.amri@kalro.org'),
    ('KALRO Food Crops Research Institute - Kabete', 'Kiambu', 'Kabete', -1.2192, 36.7383, 'Food crops research', '', ''),
    ('KALRO Food Crops Research Institute - Muguga', 'Kiambu', 'Muguga', -1.2039, 36.6408, 'Food crops research', '', ''),
    ('KALRO Food Crops Research Institute - Embu', 'Embu', 'Embu', -0.5310, 37.4575, 'Food crops (highland/mid-altitude)', '', ''),
    ('KALRO Food Crops Research Institute - Kisii', 'Kisii', 'Kisii', -0.6773, 34.7796, 'Food crops (high-rainfall zone)', '', ''),
    ('KALRO Food Crops Research Institute - Alupe', 'Busia', 'Alupe', 0.4667, 34.1167, 'Smallholder crop/livestock (serves Busia, Bungoma, Siaya)', '0203509161', 'director.fcri@kalro.org'),
    ('KALRO Horticulture Research Institute - Thika', 'Kiambu', 'Thika', -1.0396, 37.0900, 'Horticulture HQ (fruits, vegetables, flowers)', '', ''),
    ('KALRO Horticulture Research Institute - Tigoni', 'Kiambu', 'Tigoni', -1.1667, 36.7000, 'Horticulture (temperate zone)', '', ''),
    ('KALRO Horticulture Research Centre - Kibos', 'Kisumu', 'Kibos', -0.1000, 34.8500, 'Horticulture (western Kenya)', '', ''),
    ('KALRO Horticulture Research Centre - Matuga', 'Kwale', 'Matuga', -4.1667, 39.4667, 'Coastal horticulture', '', ''),
    ('KALRO Coffee Research Institute - Ruiru', 'Kiambu', 'Ruiru', -1.1500, 36.9667, 'Coffee research (HQ)', '', ''),
    ('KALRO Coffee Research Centre - Mariene', 'Meru', 'Meru', 0.0469, 37.6500, 'Coffee (Mt. Kenya region)', '', ''),
    ('KALRO Coffee Research Centre - Koru', 'Kericho', 'Koru', -0.1167, 35.3000, 'Coffee (western highlands)', '', ''),
    ('KALRO Coffee Research Centre - Namwela', 'Bungoma', 'Namwela', 0.5635, 34.5606, 'Coffee (western Kenya)', '', ''),
    ('KALRO Tea Research Institute - Kericho', 'Kericho', 'Kericho', -0.3667, 35.2833, 'Tea (HQ)', '', ''),
    ('KALRO Sugar Research Institute - Kibos', 'Kisumu', 'Kibos', -0.1000, 34.8500, 'Sugarcane (HQ)', '', ''),
    ('KALRO Industrial Crops Research Institute - Mwea Tabere', 'Kirinyaga', 'Mwea', -0.6833, 37.3500, 'Cotton, rice', '', ''),
    ('KALRO Industrial Crops Research Institute - Molo', 'Nakuru', 'Molo', -0.2500, 35.7333, 'Pyrethrum', '', ''),
    ('KALRO Industrial Crops Research Institute - Mtwapa', 'Kilifi', 'Mtwapa', -3.9333, 39.7500, 'Coconut, cashew, sisal, oil palm, sericulture', '', ''),
    ('KALRO Beef Research Institute - Lanet', 'Nakuru', 'Lanet', -0.2667, 36.1333, 'Beef cattle & pasture (HQ)', '+254 20 8044936', 'director.bri@kalro.org'),
    ('KALRO Beef Research Centre - Garissa', 'Garissa', 'Garissa', -0.4569, 39.6583, 'Beef cattle (arid zone)', '', ''),
    ('KALRO Beef Research Centre - Mariakani', 'Kilifi', 'Mariakani', -3.8667, 39.4667, 'Beef cattle (coastal)', '', ''),
    ('KALRO Beef Research Centre - Transmara', 'Narok', 'Kilgoris', -1.0333, 34.9333, 'Sahiwal cattle, Red Maasai sheep, apiary', '', ''),
    ('KALRO Sheep, Goat and Camel Research Institute - Marsabit', 'Marsabit', 'Marsabit', 2.3346, 37.9899, 'Sheep, goats, camels (arid zone HQ)', '', ''),
    ('KALRO Sheep and Goat Research Centre - Buchuma', 'Taita Taveta', 'Buchuma', -3.6500, 38.9833, 'Sheep and goat breeding', '', ''),
    ('KALRO Non-Ruminant Research Institute - Kakamega', 'Kakamega', 'Kakamega', 0.2827, 34.7519, 'Poultry, pigs, rabbits', '', ''),
    ('KALRO Apiculture Research Institute - Perkerra', 'Baringo', 'Marigat', 0.4696, 35.9803, 'Beekeeping/honey (HQ)', '', ''),
    ('KALRO Arid and Range Lands Research Institute - Kiboko', 'Makueni', 'Kiboko', -2.2167, 37.7167, 'ASAL crop & livestock systems (HQ)', '', ''),
    ('KALRO Veterinary Science Research Institute - Muguga', 'Kiambu', 'Muguga', -1.2039, 36.6408, 'Animal health & disease (HQ)', '+254 722 206986', 'info@kalro.org'),
    ('KALRO Genetic Resources Research Institute - Muguga', 'Kiambu', 'Muguga South', -1.2039, 36.6408, 'National genebank, genetic resource conservation', '', ''),
]

DAIRY_DISEASES = [
    (
        'East Coast Fever', 'Dairy cattle', 'skull-outline',
        'High fever, swollen lymph nodes (especially behind the ear/jaw), laboured breathing, discharge from '
        'eyes and nose, loss of appetite, sudden drop in milk yield. Often fatal within 1-3 weeks if untreated.',
        'A tick-borne parasite (Theileria parva), spread by the brown ear tick. One of the biggest killers of '
        'cattle in East Africa, especially exotic and crossbred dairy animals with little natural resistance.',
        'Regular acaricide (tick control) spraying or dipping on a strict schedule, pasture management to reduce '
        'tick numbers, and the ECF infection-and-treatment vaccine where available through your county vet office.',
        'Needs prompt veterinary treatment with specific anti-theilerial drugs - the sooner treatment starts after '
        'symptoms appear, the better the survival odds. Do not wait; call a vet as soon as you suspect it.',
        'KALRO Veterinary Science Research Institute / Kenya Veterinary Board guidance', 'East Coast Fever cattle Kenya symptoms treatment',
    ),
    (
        'Mastitis', 'Dairy cattle', 'medical-outline',
        'Swollen, hot, painful udder or quarter; watery, clotted or bloody milk; reduced yield; sometimes fever '
        'and a sick-looking cow. Subclinical cases show no visible signs but raise the milk\'s somatic cell count.',
        'Usually a bacterial infection entering through the teat canal, linked to poor milking hygiene, dirty '
        'bedding, or udder injury.',
        'Clean, dry bedding; disinfect teats before and after milking (pre- and post-dip); milk infected cows '
        'last or separately; cull chronically infected quarters; check milking equipment for damage.',
        'Mild cases often clear with improved hygiene alone; infected quarters usually need antibiotic treatment '
        'from a vet, and milk must be withheld from sale during and after treatment per the withdrawal period.',
        'KALRO Dairy Research Institute guidance', 'mastitis dairy cow treatment prevention Kenya',
    ),
    (
        'Foot and Mouth Disease (FMD)', 'Dairy cattle', 'warning-outline',
        'Fever, blisters and sores on the mouth, tongue, gums and between the hooves, excessive drooling, '
        'lameness, sharp drop in milk production. Spreads very fast through a herd.',
        'A highly contagious virus, spread by direct contact, contaminated equipment, vehicles, or people moving '
        'between farms.',
        'Vaccination where a county outbreak programme is running, strict control of animal movement onto the '
        'farm, quarantine of any new animal, and disinfecting boots/equipment between farms.',
        'No cure for the virus itself - report suspected cases to your county veterinary office immediately (it '
        'is a notifiable disease in Kenya); supportive care (soft feed, wound care) while the outbreak is managed.',
        'Directorate of Veterinary Services (Kenya) notifiable disease guidance', 'foot and mouth disease cattle Kenya',
    ),
    (
        'Lumpy Skin Disease', 'Dairy cattle', 'bandage-outline',
        'Firm, round skin nodules (1-5cm) over the body, fever, swollen lymph nodes, reduced milk yield, '
        'sometimes swollen legs and reluctance to move.',
        'A pox virus spread mainly by biting flies, mosquitoes and ticks.',
        'Vaccination ahead of the rainy/high-fly season, insect and tick control, and isolating new or sick '
        'animals.',
        'No specific antiviral cure - supportive treatment for fever and secondary infections under veterinary '
        'guidance, plus good nursing (soft feed and water) until nodules heal.',
        'Kenya Directorate of Veterinary Services guidance', 'lumpy skin disease cattle Kenya vaccine',
    ),
    (
        'Brucellosis', 'Dairy cattle', 'alert-circle-outline',
        'Late-term abortion (often in the last trimester), retained placenta, reduced fertility, swollen joints '
        'in some animals. Many infected cattle show no obvious symptoms otherwise.',
        'A bacterial infection, often introduced by buying an infected animal or through contact with an '
        'infected herd; it also spreads to people (zoonotic) through raw milk or contact with birth fluids.',
        'Buy replacement animals only from tested, brucellosis-free herds; test new animals before adding them '
        'to the herd; always boil or pasteurize milk before drinking; handle afterbirth/aborted material with gloves.',
        'No effective treatment in cattle - confirmed cases are usually managed by culling to protect the rest '
        'of the herd and the people on the farm; this must go through your vet, as it is a public-health concern too.',
        'Kenya Veterinary Board / zoonotic disease guidance', 'brucellosis cattle Kenya prevention',
    ),
    (
        'Milk Fever (Hypocalcemia)', 'Dairy cattle', 'pulse-outline',
        'Usually within 72 hours of calving: weakness, cold ears, muscle tremors, the cow going down and unable '
        'to stand, reduced appetite. A high-yielding cow soon after calving is most at risk.',
        'A sudden drop in blood calcium as the cow starts producing colostrum/milk faster than she can mobilise '
        'calcium reserves - most common in older, high-producing dairy cows.',
        'Balanced dry-period feeding (avoid excess calcium just before calving), and calcium/mineral supplementation '
        'timed around calving as advised by a vet or nutritionist.',
        'An emergency - a vet-administered calcium infusion (intravenous or under-the-skin) usually brings a '
        'rapid recovery; call a vet as soon as a freshly-calved cow goes down.',
        'KALRO Dairy Research Institute guidance', 'milk fever dairy cow treatment',
    ),
    (
        'Bloat (Ruminal Tympany)', 'Dairy cattle', 'ellipse-outline',
        'Visibly swollen left side of the abdomen, distress, rapid breathing, reduced appetite; severe cases can '
        'be fatal within hours from pressure on the lungs and heart.',
        'A build-up of gas in the rumen, often from grazing lush young legumes/Napier grass, sudden feed changes, '
        'or a blocked oesophagus.',
        'Introduce lush pasture or fresh Napier gradually, provide roughage/hay alongside rich green feed, and '
        'avoid sudden feed changes.',
        'Mild cases may pass with walking the animal and drenching with an anti-bloat/vegetable oil remedy; '
        'severe, rapidly swelling cases are an emergency needing a vet urgently (may need a rumen puncture).',
        'KALRO Dairy Research Institute guidance', 'bloat cattle emergency treatment',
    ),
    (
        'Anaplasmosis (Gall Sickness)', 'Dairy cattle', 'thermometer-outline',
        'Fever, pale or yellow (jaundiced) gums and eyes, weakness, reduced appetite, dark urine in severe cases, '
        'sudden drop in milk yield.',
        'A tick-borne blood parasite (Anaplasma), spread mainly by ticks and sometimes contaminated instruments '
        '(needles, dehorning tools).',
        'Consistent tick control (spraying/dipping), disinfecting instruments between animals, and controlled '
        'grazing to reduce tick exposure.',
        'Responds well to antibiotics (tetracyclines) given early by a vet, often alongside supportive fluids for '
        'weak animals.',
        'KALRO Veterinary Science Research Institute guidance', 'anaplasmosis gall sickness cattle treatment',
    ),
]

CROP_DISEASES = [
    (
        'Napier Stunt Disease', 'Napier grass', 'leaf-outline',
        'Stunted, bunched growth with short internodes, yellowing/pale leaves, thin stems, and a sharp drop in '
        'the amount of fodder harvested.',
        'A phytoplasma (bacteria-like organism) spread by leafhopper insects and by planting infected cuttings.',
        'Plant only certified, disease-free splits/cuttings from a trusted source (e.g. a KALRO-linked bulking '
        'site), rotate to a resistant/tolerant variety where available, and remove and burn severely stunted clumps.',
        'No cure once a plant is infected - remove and destroy affected clumps to slow spread, and replant the '
        'area with clean planting material.',
        'KALRO Food Crops Research Institute Napier grass guidance', 'napier grass stunt disease Kenya control',
    ),
    (
        'Napier Head Smut', 'Napier grass', 'flower-outline',
        'A black, powdery mass replacing the normal flower head ("smut" gall), often with excessive tillering '
        'and stunted growth around the affected shoot.',
        'A fungal disease (Ustilago kamerunensis) spread by wind-borne spores and infected planting material.',
        'Use clean, certified planting material, remove and burn smutted heads before they release spores, and '
        'avoid moving cuttings from an infected field to a clean one.',
        'No chemical cure at farm level - control is by sanitation (destroying infected heads/clumps early) and '
        'replanting with clean material.',
        'KALRO Food Crops Research Institute Napier grass guidance', 'napier grass head smut control',
    ),
    (
        'Maize Lethal Necrosis (MLN)', 'Maize', 'nutrition-outline',
        'Yellowing starting from the leaf base moving upward, a "dead heart" appearance, severe stunting, and '
        'small, poorly filled or no cobs at all.',
        'A combination of two viruses (maize chlorotic mottle virus plus a cereal virus), spread by insects '
        '(thrips, aphids) and contaminated seed.',
        'Plant MLN-tolerant/resistant certified seed varieties, rotate maize with a non-cereal crop, control the '
        'insect vectors, and remove volunteer maize plants that can carry the virus between seasons.',
        'No cure once infected - uproot and destroy badly affected plants to reduce the source of infection for '
        'neighbouring fields, and plan tolerant varieties for the next season.',
        'KALRO Food Crops Research Institute (Kitale/Katumani) guidance', 'maize lethal necrosis disease Kenya',
    ),
    (
        'Fall Armyworm', 'Maize', 'bug-outline',
        'Ragged holes in leaves, sawdust-like frass (droppings) in the funnel, damaged growing points, and '
        'caterpillars visible in the whorl - young plants can be killed outright.',
        'A caterpillar pest (Spodoptera frugiperda) that spread across Africa in recent years; moths lay eggs on '
        'leaves and larvae feed inside the whorl where they are hard to reach.',
        'Scout fields weekly from emergence, intercrop with legumes where practical, encourage natural predators, '
        'and plant early so crops outgrow the most vulnerable stage before peak pest pressure.',
        'For heavy infestations, an approved insecticide applied directly into the whorl (following label rates) '
        'is most effective - ask your county agriculture office which product is currently recommended.',
        'FAO / KALRO fall armyworm management guidance for Kenya', 'fall armyworm maize control Kenya',
    ),
    (
        'Maize Streak Virus', 'Maize', 'flash-outline',
        'Narrow, broken yellow/white streaks running along the leaf veins, stunted plants, and poor cob '
        'development if infected early.',
        'A virus transmitted by maize leafhoppers, often worse after a dry spell followed by rain that boosts '
        'leafhopper numbers.',
        'Plant tolerant varieties, plant early with the first reliable rains, control leafhoppers, and avoid '
        'staggered planting near older infected maize.',
        'No cure once infected - remove badly affected plants early in the season and focus on tolerant varieties '
        'and vector control for future plantings.',
        'KALRO Food Crops Research Institute guidance', 'maize streak virus control Kenya',
    ),
    (
        'Bean Anthracnose', 'Beans', 'water-outline',
        'Dark, sunken spots with a reddish-brown border on pods, stems and leaves; infected pods often show '
        'darkened veins and shrivelled seeds.',
        'A seed- and rain-splash-borne fungus, worse in wet weather and when infected seed is replanted.',
        'Plant certified, disease-free seed, rotate beans with a non-legume crop for at least two seasons, and '
        'avoid working in the field when foliage is wet (spreads spores).',
        'Remove and destroy heavily infected plants; a recommended fungicide can protect the remaining crop if '
        'applied early - check current recommendations with your county agriculture office.',
        'KALRO Food Crops Research Institute bean pathology guidance', 'bean anthracnose control Kenya',
    ),
    (
        'Late Blight', 'Potatoes / Tomatoes', 'rainy-outline',
        'Dark, water-soaked patches on leaves that quickly turn brown/black, a white fungal fuzz on the leaf '
        'underside in humid weather, and blackened, rotting patches on tubers or fruit.',
        'A fungus-like pathogen (Phytophthora infestans) that spreads explosively in cool, wet, humid conditions.',
        'Plant certified disease-free seed potatoes/tomato seedlings, avoid overhead irrigation late in the day, '
        'space plants for good airflow, and rotate away from potatoes/tomatoes for at least one season.',
        'Remove and destroy infected plants/tubers promptly; a protectant fungicide programme started before '
        'symptoms appear is far more effective than spraying after an outbreak - ask your local stockist for the '
        'currently recommended product.',
        'KALRO Horticulture Research Institute guidance', 'late blight potato tomato control Kenya',
    ),
    (
        'Diamondback Moth', 'Kales / Cabbage (Sukuma wiki)', 'leaf-outline',
        'Small, ragged "windowpane" holes in leaves left by tiny green caterpillars, worse on the underside of '
        'leaves and on young plants.',
        'A moth pest whose larvae feed on brassica leaves; it has developed resistance to many common '
        'insecticides in parts of Kenya, so control needs care.',
        'Rotate away from brassicas, intercrop with a non-host crop, encourage natural enemies (parasitic wasps), '
        'and avoid relying on the same insecticide repeatedly (rotate modes of action to slow resistance).',
        'If spraying is needed, use a recommended product and rotate between different chemical groups season to '
        'season - ask your county agriculture office which products still work well locally.',
        'KALRO Horticulture Research Institute guidance', 'diamondback moth kale cabbage control Kenya',
    ),
]

GUIDES = [
    (
        'silage', 'Making Napier grass silage', 'archive-outline',
        'Preserve surplus Napier grass as silage so there is quality fodder in the dry season.',
        'Harvest Napier grass at the right stage - about 1-1.2m tall, before it gets too fibrous (roughly 8-10 weeks of regrowth).\n'
        'Wilt the cut grass in the sun for a few hours to reduce moisture, then chop it into 2-5cm pieces (shorter pieces pack tighter and preserve better).\n'
        'Mix in a fermentable energy source if available, e.g. molasses (about 3-5% of fresh weight) or crushed maize/dairy meal, to feed the fermenting bacteria.\n'
        'Pack the chopped, wilted material tightly into a pit, trench, or silage bag in thin layers, compacting each layer firmly to push out air.\n'
        'Seal completely with polythene sheeting and weigh it down (soil, tyres, sandbags) so no air or water can get in.\n'
        'Leave sealed for at least 21 days before opening - the silage should smell pleasantly sour/sweet, not rotten, and be greenish-brown.\n'
        'Once opened, feed from the face daily and re-cover after each feeding to limit spoilage.',
        'A good silage has a firm texture and a sweet-sour smell - a bad, ammonia-like smell or slimy texture means it spoiled and should not be fed.\n'
        'Never leave the silage pit open to rain or air for long once you start feeding from it.',
        'KALRO Dairy Research Institute silage-making guidance', 'napier grass silage making Kenya step by step',
    ),
    (
        'value_addition', 'Making yogurt from milk', 'nutrition-outline',
        'Turn fresh milk into yogurt for a longer shelf life and a higher-value product to sell.',
        'Start with clean, fresh milk and heat it to about 85°C (just below boiling), stirring so it doesn\'t stick or burn.\n'
        'Hold it at that temperature for about 5-10 minutes - this improves the final texture.\n'
        'Cool the milk down to about 43-45°C (warm to the touch, not hot).\n'
        'Stir in a starter culture - either a commercial yogurt culture or 2-3 tablespoons of plain live yogurt per litre of milk.\n'
        'Pour into clean, covered containers and keep warm (around 40-43°C) for 4-8 hours undisturbed, until it sets and thickens.\n'
        'Once set, refrigerate promptly to stop further fermentation and slow spoilage.',
        'Keep a little of each good batch aside as starter for the next one, but refresh with a commercial culture every few batches to keep quality consistent.\n'
        'Cleanliness of all utensils is the single biggest factor in a safe, good-tasting batch.',
        'KALRO / Dairy value-addition extension guidance', 'making yogurt at home Kenya small scale',
    ),
    (
        'value_addition', 'Making mala (fermented milk)', 'cafe-outline',
        'Make mala (traditional naturally-fermented milk), a simple, widely-sold value-added dairy product.',
        'Use clean, fresh milk, and boil it briefly to kill unwanted bacteria, then cool to room temperature.\n'
        'Pour into a clean container and add a small amount of a previous good batch of mala (or a small amount of natural yogurt) as a starter.\n'
        'Cover the container with a clean cloth (not airtight) and leave it undisturbed in a warm spot for 12-24 hours until it thickens and develops a mild sour taste.\n'
        'Once set, refrigerate to slow further souring, or sell/consume promptly.',
        'A too-long fermentation time makes it overly sour and can encourage unwanted bacteria - taste-check after 12 hours.\n'
        'Always use a fresh, good-smelling starter batch; if a batch smells off, don\'t use it to start the next one.',
        'Traditional dairy value-addition practice, extension guidance', 'making mala fermented milk Kenya',
    ),
    (
        'value_addition', 'Making ghee (samli) from milk', 'flame-outline',
        'Turn surplus milk fat into ghee (clarified butter), which stores far longer than fresh milk or cream.',
        'Separate cream from fresh milk (let it settle and skim, or use a cream separator) and collect it over a few days if needed, keeping it refrigerated.\n'
        'Let the collected cream sour slightly at room temperature, then churn it (by hand or machine) until butterfat separates from the buttermilk.\n'
        'Drain off the buttermilk (it can still be used for cooking or drinking) and rinse the butter solids with clean water.\n'
        'Melt the butter slowly over low heat in a clean pot, stirring occasionally, until it stops foaming and the milk solids sink and turn golden-brown at the bottom.\n'
        'Remove from heat once the liquid is clear golden and smells nutty (not burnt), and strain through a clean cloth into a dry, sterilised jar.\n'
        'Store the sealed ghee in a cool, dry place - it does not need refrigeration and keeps for months.',
        'Cook the butter on low heat and watch closely near the end - it can burn quickly once the water has cooked off.\n'
        'Only use clean, dry containers for storage; any moisture shortens shelf life.',
        'Traditional dairy value-addition practice, extension guidance', 'making ghee samli from milk Kenya',
    ),
    (
        'land_prep', 'Preparing land before planting', 'construct-outline',
        'Get a field ready so seeds or fodder cuttings establish well and compete less with weeds.',
        'Clear the field of the previous crop\'s residue, weeds and debris - residue can be incorporated as mulch/organic matter rather than burned where possible.\n'
        'Plough or dig the soil to break up compaction and improve root penetration, ideally when the soil has some moisture but isn\'t waterlogged.\n'
        'Harrow or rake to break large clods into a finer tilth suitable for the seed or cutting size you\'re planting.\n'
        'Level the field, and where the land slopes, form contour lines or ridges across the slope to reduce soil erosion.\n'
        'Apply well-rotted manure or compost and work it into the topsoil ahead of planting, based on your soil test results.\n'
        'Mark out planting rows/spacing appropriate to the crop before the actual planting day.',
        'Prepare land 2-3 weeks ahead of the rains where possible so organic matter has time to start breaking down.\n'
        'Avoid working wet, heavy soil - it compacts more and forms hard clods once dry.',
        'KALRO land preparation extension guidance', 'land preparation before planting Kenya smallholder',
    ),
    (
        'soil_sampling', 'How to take a soil sample for testing', 'flask-outline',
        'Get an accurate soil test result so fertiliser and lime decisions are based on your field\'s real needs, not guesswork.',
        'Divide the farm into uniform zones (similar soil type, slope, and crop history) - sample each zone separately rather than mixing very different areas.\n'
        'For each zone, walk in a zig-zag pattern and take 15-20 small samples using a soil auger or clean spade, at a depth of about 0-20cm for most crops.\n'
        'Put all the small samples for one zone into a clean bucket and mix thoroughly to form one composite sample.\n'
        'Take about 500g of the mixed sample, air-dry it in the shade (never in direct sun or an oven), and place it in a clean, labelled bag.\n'
        'Label each sample clearly with the farm name, zone/field name, and date.\n'
        'Deliver samples to a soil testing lab (e.g. a KALRO centre, university lab, or accredited private lab) as soon as possible after collection.',
        'Avoid sampling right after fertiliser, manure or lime has just been applied - wait a few months for a representative result.\n'
        'Use clean tools between zones to avoid cross-contaminating samples.',
        'KALRO soil sampling and testing guidance', 'how to take soil sample for testing Kenya',
    ),
    (
        'planting', 'Planting Napier grass', 'leaf-outline',
        'Establish a new Napier grass plot for reliable dairy fodder.',
        'Choose certified, disease-free cane cuttings or root splits from a trusted, Napier-stunt-free source.\n'
        'Prepare the land as usual (clear, plough, harrow) and, where the field slopes, plant along the contour to reduce erosion.\n'
        'Plant cane cuttings at a slant with 2-3 nodes buried in the soil, or plant root splits upright, spaced roughly 0.5-1m within rows and 0.75-1m between rows.\n'
        'Apply manure or compost in the planting furrow/hole before placing the cuttings.\n'
        'Water at planting if there\'s no immediate rain, and keep the plot weeded until the young grass is well established (about 6-8 weeks).\n'
        'Allow the first cut at around 3-4 months to let the crown establish a strong root system before regular harvesting begins.',
        'Only source planting material from a field known to be free of Napier stunt disease and head smut.\n'
        'Intercropping with a legume like desmodium in the early stages can improve soil fertility and provide extra fodder.',
        'KALRO Food Crops Research Institute Napier grass guidance', 'planting napier grass Kenya spacing',
    ),
    (
        'planting', 'Planting maize', 'nutrition-outline',
        'Get maize established well for a strong, even stand and good yield.',
        'Select a certified seed variety suited to your altitude/rainfall zone and expected maturity period.\n'
        'Plant with the onset of reliable rains, at a depth of about 3-5cm.\n'
        'Space seeds appropriately for your variety - commonly around 75cm between rows and 25-30cm within the row for a medium-density stand (check the seed packet\'s recommendation).\n'
        'Apply a starter (planting) fertiliser in the planting hole/furrow, placed slightly to the side of the seed rather than in direct contact.\n'
        'Thin to one or two healthy seedlings per planting point about 2-3 weeks after emergence.\n'
        'Top-dress with nitrogen fertiliser at knee-height stage, and scout regularly for fall armyworm and other pests from emergence onward.',
        'Don\'t plant too early on unreliable rains - a false start followed by drought can force costly replanting.\n'
        'Rotate maize with a legume (beans, soybeans) where possible to help manage soil fertility and disease build-up.',
        'KALRO Food Crops Research Institute maize guidance', 'maize planting guide Kenya spacing fertilizer',
    ),
    (
        'harvesting', 'Harvesting Napier grass for feeding or silage', 'cut-outline',
        'Cut Napier grass at the right stage for the best balance of yield and feed quality.',
        'For fresh feeding, cut when the grass is about 1-1.5m tall, roughly every 6-8 weeks depending on growth rate and season.\n'
        'For silage-making, cut slightly earlier (around 1-1.2m) since younger material ferments and preserves better.\n'
        'Cut close to the ground (about 5-10cm above soil level) using a sharp panga/machete to encourage vigorous regrowth from the crown.\n'
        'Avoid cutting during very wet conditions where possible, as this can damage the crown and encourage rot.\n'
        'Feed or ensile the cut material promptly - Napier grass wilts and loses quality quickly after cutting, especially in hot weather.',
        'Cutting too late (very tall, woody stems) sharply reduces protein content and palatability for the cows.\n'
        'Rotate which section of a large plot you cut each week so the whole plot isn\'t harvested at once.',
        'KALRO Dairy Research Institute guidance', 'napier grass harvesting stage feeding',
    ),
    (
        'harvesting', 'Knowing when and how to harvest maize', 'basket-outline',
        'Time the maize harvest correctly to avoid losses from birds, rot, pests and poor grain quality.',
        'For green maize (roasting/boiling), harvest when kernels are plump and milky when pressed with a fingernail, usually 18-22 weeks after planting depending on variety.\n'
        'For dry grain, wait until the husks turn brown/papery and a black layer forms at the kernel base, then let the crop dry further in the field if weather allows.\n'
        'Harvest promptly once mature to reduce losses from birds, weevils and field rot, especially in wet weather.\n'
        'Dry harvested cobs/grain thoroughly (on a raised drying rack or tarpaulin, not directly on bare ground) before storage.\n'
        'Shell and store grain in clean, dry, pest-proof containers or bags, checking moisture is low enough to prevent mould (grain should feel hard and dry, not moisture-give the shell).',
        'Store maize away from dampness and inspect regularly for weevils or mould - early detection prevents major storage losses.\n'
        'Consider hermetic (airtight) storage bags for smallholder quantities - they significantly cut storage pest damage without chemicals.',
        'KALRO post-harvest handling guidance', 'maize harvesting drying storage Kenya',
    ),
]


def seed_content(apps, schema_editor):
    AgriCenter = apps.get_model('advisory', 'AgriCenter')
    DiseaseCatalog = apps.get_model('advisory', 'DiseaseCatalog')
    Guide = apps.get_model('advisory', 'Guide')

    for name, county, town, lat, lon, focus, phone, email in AGRI_CENTERS:
        AgriCenter.objects.create(
            name=name, county=county, town=town, latitude=lat, longitude=lon,
            coordinates_are_approximate=True, focus_area=focus, phone=phone, email=email,
            source_note='KALRO official directory (kalro.org)',
        )

    for name, affected, icon, symptoms, cause, prevention, treatment, source, search in DAIRY_DISEASES:
        DiseaseCatalog.objects.create(
            category='dairy', name=name, affected=affected, icon=icon,
            symptoms=symptoms, cause=cause, prevention=prevention, treatment=treatment,
            source_note=source, search_terms=search,
        )

    for name, affected, icon, symptoms, cause, prevention, treatment, source, search in CROP_DISEASES:
        DiseaseCatalog.objects.create(
            category='crop', name=name, affected=affected, icon=icon,
            symptoms=symptoms, cause=cause, prevention=prevention, treatment=treatment,
            source_note=source, search_terms=search,
        )

    for category, title, icon, summary, steps, tips, source, search in GUIDES:
        Guide.objects.create(
            category=category, title=title, icon=icon, summary=summary,
            steps=steps, tips=tips, source_note=source, search_terms=search,
        )


def unseed_content(apps, schema_editor):
    apps.get_model('advisory', 'AgriCenter').objects.all().delete()
    apps.get_model('advisory', 'DiseaseCatalog').objects.all().delete()
    apps.get_model('advisory', 'Guide').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('advisory', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_content, unseed_content),
    ]
