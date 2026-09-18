from django.db import migrations

# General dairy-husbandry practice, not sourced from any single commercial
# app - reflects the kind of guidance that smallholder-focused African tools
# (simple structured data entry, tape-based weight estimation, a breeding
# calendar built from logged dates) and precision-dairy European tools
# (individual animal ID discipline, structured heat detection, DIM/BCS/
# calving-interval as the core KPIs) converge on.

LESSONS = [
    (
        1, 'Dairy farming terminology', 'list-outline',
        'The words you will see throughout this app and from your vet or extension officer.',
        '\n'.join([
            "Every trade has its own shorthand - dairy farming is no exception. Knowing these terms will "
            "make the rest of this course, and the rest of FarmIQ, much easier to follow.",
            '## Why it matters',
            "Your vet, extension officer, or the app itself will use these words constantly. A farmer who "
            'doesn\'t yet know "DIM" or "dry period" can still run a good farm, but will spend a lot of time '
            'guessing at instructions that would otherwise be obvious.',
            'The glossary below covers the terms that come up most often - refer back to it any time a '
            "later lesson uses a word you don't recognise.",
        ]),
        '\n'.join([
            'Days in milk (DIM): Number of days since a cow last calved - the single biggest driver of how '
            'much milk she gives on any given day.',
            'Dry period: The 6-8 weeks before calving when a cow is deliberately not milked, so her body '
            'can recover and prepare for the next lactation.',
            'Freshening: When a cow calves and starts a new lactation.',
            "Heifer: A young female that hasn't calved yet.",
            'Calf: A cow or bull under about 6-12 months old, before weaning is complete.',
            "Estrus (heat): The roughly one-day window in a cow's ~21-day cycle when she is fertile and "
            'will accept mating.',
            'Service: Mating a cow, whether by a bull (natural service) or artificial insemination (AI).',
            'Calving interval: The time between one calving and the next - shorter is generally more '
            'profitable.',
            'Body condition score (BCS): A 1-5 visual/hands-on score of how much fat cover a cow is '
            'carrying.',
            "Colostrum: The thick, antibody-rich first milk a cow produces right after calving - essential "
            "for a newborn calf's immunity.",
            'Somatic cell count (SCC): A lab count of white blood cells in milk - the standard early-'
            'warning indicator of mastitis and milk quality.',
            'Heart girth: The circumference of the chest just behind the front legs - used to estimate '
            'liveweight with a tape when no scale is available.',
        ]),
        'dairy farming terms glossary for beginners',
    ),
    (
        2, 'Identifying and tagging your herd', 'pricetag-outline',
        'Every record starts with a permanent, unique animal ID.',
        '\n'.join([
            'Before you can track weight, health, milk or breeding for a cow, she needs a permanent, '
            'unique identity. This is the single most important habit in herd record-keeping - every other '
            "record in this app is only useful if it's tied to the right animal.",
            '## Choosing an ID system',
            'Use a visible ear tag with a short, unique code (e.g. C-001, C-002) rather than a name alone - '
            "names get reused or forgotten, tag numbers don't.",
            "Tag calves within their first few days of life, before they're mixed with the rest of the "
            'herd.',
            'Keep a record of which tag number belongs to which animal - this app does that for you '
            'automatically once she is registered.',
            "If an animal is registered with a breed society, record that registration number too - it's a "
            'separate, permanent ID that follows her even if her tag is ever replaced.',
            '## Why FarmIQ enforces this',
            "Every cow record in FarmIQ requires a tag ID that's unique on your farm - this keeps a milk "
            'record, a health record, or a weight record from ever being attributed to the wrong animal as '
            'your herd grows.',
        ]),
        '',
        'ear tag cattle identification smallholder dairy',
    ),
    (
        3, 'Daily and weekly herd inspection', 'eye-outline',
        'A short, structured walk-through that catches problems while they are still cheap to fix.',
        '\n'.join([
            'A short, structured walk through the herd catches problems while they are still cheap and '
            'easy to treat. Most experienced dairy farmers do a version of this every single day, almost '
            'without thinking about it.',
            '## Daily, at every milking or feeding',
            "Appetite: is she eating and ruminating normally? A cow that isn't chewing her cud, or is "
            'standing apart from the group, is often the first sign something is wrong.',
            'Gait: watch her walk. Lameness is one of the most under-reported problems on smallholder '
            'farms and directly cuts milk yield.',
            'Udder: check for heat, swelling, or hardness before milking, and watch the milk itself for '
            'clots, blood, or wateriness.',
            'Discharge: any unusual discharge from the eyes, nose or vulva is worth a closer look.',
            'Manure: consistency tells you a lot - watery scours or unusually hard, dry manure both signal '
            'a diet or health issue worth investigating.',
            'Coat and skin: a dull, rough coat or visible ticks/lice often shows up before other symptoms '
            'do.',
            '## Weekly',
            'Body condition score the whole herd (see the next lesson) so you catch a slow decline before '
            'it becomes a crisis.',
            'Weigh calves and any cow you are concerned about (see the weighing lesson).',
            "Review the last week's milk and feed records for any cow whose yield dropped sharply - that "
            'is often the earliest measurable sign of a health problem.',
            '## When to call a vet',
            'A sudden drop in milk yield, high fever, refusal to eat, being down and unable to rise, or '
            'blood in milk or manure are all reasons to call a vet immediately rather than wait and see.',
        ]),
        '',
        'dairy cow health check routine signs of illness',
    ),
    (
        4, 'Weighing your cow with a tape', 'resize-outline',
        'A heart-girth tape measurement, and how FarmIQ turns it into an estimated weight.',
        '\n'.join([
            'A weighbridge is the most accurate way to weigh cattle, but very few smallholder farms have '
            'one. A simple tape measure around the chest gets you a usable estimate - accurate enough to '
            "track trends over time, even if it isn't lab-precise.",
            '## How to measure heart girth',
            'Stand the cow square on level ground, calm and not eating.',
            'Wrap the tape snugly (not tight) around her chest, directly behind the front legs and '
            'shoulder blades.',
            'Read the measurement in centimetres at the point the tape meets itself.',
            'Take two measurements and use the average - a stressed or badly-positioned animal can shift '
            'the reading by several centimetres.',
            '## Turning the measurement into a weight',
            'FarmIQ does this calculation for you: log a weight record with method "Heart-girth tape", '
            'enter the girth measurement, and leave the weight field blank - the app estimates liveweight '
            'automatically using the same girth-cubed formula printed on physical cattle weigh tapes.',
            'This is an estimate, not a substitute for a scale - use it to track whether an animal is '
            'gaining, holding, or losing condition over time, not as an exact figure.',
            '## How often to weigh',
            'Calves: every 1-2 weeks, to catch slow growth early while it is still easy to correct with '
            'feed.',
            'Growing heifers: monthly, to track whether they are on course to reach breeding weight '
            '(roughly 55-60% of mature bodyweight) at the right age.',
            'Adult cows: monthly, or around key events such as drying off and calving, to watch body '
            'condition alongside milk yield.',
        ]),
        '',
        'how to weigh a cow with a tape measure heart girth',
    ),
    (
        5, 'Body condition scoring (BCS)', 'body-outline',
        'A hands-on 1-5 scale for tracking nutrition and health independent of frame size.',
        '\n'.join([
            'Body condition score (BCS) is a hands-on and visual estimate, on a 1 (emaciated) to 5 (obese) '
            "scale, of how much fat cover a cow is carrying. Unlike weight alone, it isn't affected by "
            'frame size or gut fill, which makes it a better day-to-day check on nutrition and health.',
            '## What to check',
            'Loin: run a hand along the spine and short ribs behind the last rib - in a thin cow you will '
            'feel sharp, prominent bones; in a fat cow, a smooth, well-padded surface.',
            'Tailhead: the area around the tailhead either shows a visible cavity (thin) or is smoothly '
            'filled in (fat).',
            'Ribs: whether individual ribs are visible or easily felt versus covered and hard to '
            'distinguish.',
            '## Target scores through the cycle',
            'A score around 3.0-3.5 at calving is typical for most dairy breeds - low enough to avoid '
            'calving and metabolic problems, high enough to support early lactation.',
            'A moderate, gradual drop to around 2.5-3.0 in early lactation is normal as she uses body '
            'reserves to support milk production.',
            'Rebuild condition through mid-to-late lactation so she is back to 3.0-3.5 by the time she is '
            'dried off - trying to fatten her up in the final weeks before calving instead causes more '
            'problems than it solves.',
            "A cow that is losing condition sharply, or stays thin through a full lactation, needs a "
            'closer look at her diet, parasite load, or an underlying health issue.',
        ]),
        '',
        'body condition scoring dairy cattle guide',
    ),
    (
        6, 'Understanding the estrus cycle & heat detection', 'calendar-outline',
        "The ~21-day cycle, the signs to watch for, and why timely detection shortens calving interval.",
        '\n'.join([
            "Getting a cow back in calf promptly keeps her calving interval short, which is one of the "
            'biggest levers on a dairy herd\'s profitability. That starts with reliably spotting when she '
            'is in heat.',
            '## The cycle',
            "A cow that isn't pregnant cycles roughly every 21 days (18-24 days is normal), with standing "
            'heat - the fertile window - lasting only 12-18 hours.',
            'Missing that window means waiting another full cycle, so a system for watching for and '
            "recording heat signs matters more than any single day's observation.",
            '## Signs to watch for',
            'Standing to be mounted by other cows is the single most reliable sign - a cow that stands '
            'still and lets others mount her is almost certainly in heat.',
            'Restlessness, frequent bellowing, and a drop in appetite or milk yield.',
            'Clear, stringy mucus discharge from the vulva.',
            'Swollen, reddened vulva, and mounting other cows herself even if not standing to be mounted.',
            '## Timing service',
            'The long-standing "AM/PM rule" - a cow seen in standing heat in the morning is served that '
            'evening, one seen in standing heat in the evening is served the next morning - remains a '
            'reliable practical guide for natural service or AI timing.',
            '## Logging it',
            'Log every heat you observe as a "Heat observed" event in the Breeding calendar, even if you '
            "don't serve her that cycle - a pattern of dates lets you, and the app, predict her next "
            'expected heat around 21 days later, so you are watching at the right time instead of by '
            'chance.',
        ]),
        '',
        'signs of heat in dairy cows estrus cycle detection',
    ),
    (
        7, 'The dry period & transition cow care', 'pause-circle-outline',
        'Why cows need about 60 days dry before calving, and what "dried off" means in practice.',
        '\n'.join([
            'A dry period - a deliberate stretch of about 6-8 weeks (roughly 60 days) with no milking '
            "before the next calving - isn't wasted time. It's when the udder tissue regenerates and the "
            "cow builds the reserves she'll draw on through the next lactation.",
            '## Why it matters',
            'Cows dried off too briefly, or not at all, tend to produce noticeably less milk in the '
            'following lactation, and face higher risk of metabolic disease around calving.',
            'Drying off too early wastes days of milk unnecessarily, so the target window matters in both '
            'directions.',
            '## How to dry a cow off',
            'Stop milking abruptly rather than gradually reducing sessions - abrupt drying off is now the '
            "standard recommendation for most cows, as it triggers the udder's natural shutdown signal "
            'fastest.',
            "Move her to a separate group or paddock away from the milking herd so she isn't stimulated to "
            'let down milk.',
            'Watch her udder for the first week or two for any heat, swelling or discomfort, which can '
            'signal mastitis setting in during the dry period.',
            '## Feeding through the transition',
            'Dry cow rations are lower-energy than a milking ration for most of the dry period, shifting '
            'to a "close-up" transition diet in the final 2-3 weeks before calving to prepare the rumen '
            'for the demands of early lactation.',
            'Sudden feed changes right before or after calving are a common trigger for metabolic problems '
            '- any ration change should be gradual.',
            '## Logging it',
            'Log a "Dried off" event in the Breeding calendar the day you stop milking - FarmIQ uses that '
            'to mark her status as Dry and to estimate her calving and next dry-off dates going forward.',
        ]),
        '',
        'dry period dairy cow management transition feeding',
    ),
    (
        8, 'Calving preparation & the newborn calf', 'heart-outline',
        'Spotting the signs, preparing a clean calving area, and colostrum in the first hours.',
        '\n'.join([
            "Most of the risk in a cow's reproductive cycle is concentrated in the days around calving - "
            'for her and for the calf. A little preparation goes a long way.',
            '## Signs calving is approaching',
            'Udder filling and the teats becoming waxy or swollen, typically in the final 1-2 weeks.',
            'Relaxation and swelling around the tailhead and vulva in the final days.',
            'Restlessness, isolating herself from the herd, and lying down and getting up repeatedly as '
            'labour begins.',
            '## Preparing the calving area',
            'Move her to a clean, dry, well-bedded area away from the rest of the herd a few days before '
            'her due date.',
            'Keep the area free of mud and manure buildup - most newborn infections trace back to a dirty '
            'calving environment.',
            "Have clean towels, a working stomach tube or bottle, and a vet's number on hand before she is "
            'due, not after labour starts.',
            '## The critical first hours',
            'Colostrum within the first 2 hours of life, and again within 12 hours, is the single most '
            "important thing you can do for a newborn calf - her gut can only absorb colostrum's "
            'antibodies efficiently for a short window after birth.',
            "If the calf hasn't nursed within a couple of hours, hand-milk colostrum from the dam and feed "
            'it by bottle or tube rather than waiting.',
            'Dip the navel in iodine or a similar disinfectant soon after birth to reduce infection risk.',
            "Weigh the calf in her first day or two - that becomes the baseline for tracking her growth "
            'against the weighing schedule from the earlier lesson.',
        ]),
        '',
        'preparing for cow calving newborn calf care colostrum',
    ),
    (
        9, 'Record-keeping: why every entry matters', 'bulb-outline',
        'How your logged records feed FarmIQ\'s own predictions - and your own decisions.',
        '\n'.join([
            'Every record you log - weight, health, milk, feed, or a breeding event - does more than sit '
            'in a table. Together they build the history that makes the rest of FarmIQ, and your own '
            'decision-making, sharper over time.',
            '## What your records feed into',
            "Milk predictions use each cow's days-in-milk, feed and historical yield to forecast "
            'production - the more consistently you log, the more accurate that forecast becomes.',
            "The credit score module draws on your farm's real production and financial history - "
            'consistent record-keeping is itself an asset when you need to demonstrate the farm\'s track '
            'record.',
            'The breeding calendar in this app is entirely built from the events you log - skip logging a '
            'heat or a service, and the app has nothing to estimate a due date from.',
            '## Habits that make records worth trusting',
            'Log records the same day, not from memory a week later - dates and quantities both drift '
            'quickly.',
            'Log every animal, not just the ones with obvious problems - a full, unbroken history is what '
            'lets you, or the app, spot a slow decline early, before it becomes an emergency.',
            'Correct a mistake by editing the record, rather than leaving it wrong and adding a note '
            'elsewhere - future reports and predictions only see the data, not your intentions.',
            '## Where to go from here',
            'You now have the vocabulary, the inspection routine, and the recording habits this course '
            "set out to cover. From here, the disease catalog, how-to guides, and your farm's own "
            'dashboards are the place to keep building on it.',
        ]),
        '',
        'importance of record keeping dairy farm management',
    ),
]


def seed_learning_path(apps, schema_editor):
    LearningPath = apps.get_model('advisory', 'LearningPath')
    LearningLesson = apps.get_model('advisory', 'LearningLesson')

    path = LearningPath.objects.create(
        slug='getting-started',
        title='Getting started with your dairy farm',
        description=(
            'Terminology, herd inspection, weighing with a tape, and the breeding calendar - the '
            'essentials for a new dairy farmer.'
        ),
        icon='school-outline',
    )
    LearningLesson.objects.bulk_create([
        LearningLesson(
            path=path, order=order, title=title, icon=icon, summary=summary,
            content=content, key_terms=key_terms, search_terms=search_terms,
        )
        for order, title, icon, summary, content, key_terms, search_terms in LESSONS
    ])


def unseed_learning_path(apps, schema_editor):
    apps.get_model('advisory', 'LearningPath').objects.filter(slug='getting-started').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('advisory', '0005_learningpath_learninglesson'),
    ]

    operations = [
        migrations.RunPython(seed_learning_path, unseed_learning_path),
    ]
