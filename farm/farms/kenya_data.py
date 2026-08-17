"""Kenya's 47 counties with a handful of well-known towns in each, used to
power the cascading Country -> County -> Location dropdowns on the farm
forms. This is the app's only supported country's admin-division data for
now; COUNTY_TOWNS is deliberately a plain dict (not a database table) since
it's fixed, public reference data that never needs editing at runtime."""

COUNTY_TOWNS = {
    'Baringo': ['Kabarnet', 'Eldama Ravine', 'Marigat'],
    'Bomet': ['Bomet', 'Sotik', 'Longisa'],
    'Bungoma': ['Bungoma', 'Webuye', 'Kimilili'],
    'Busia': ['Busia', 'Malaba', 'Nambale'],
    'Elgeyo-Marakwet': ['Iten', 'Kapsowar', 'Chebiemit'],
    'Embu': ['Embu', 'Runyenjes', 'Siakago'],
    'Garissa': ['Garissa', 'Dadaab', 'Masalani'],
    'Homa Bay': ['Homa Bay', 'Mbita', 'Oyugis'],
    'Isiolo': ['Isiolo', 'Merti', 'Garbatulla'],
    'Kajiado': ['Kajiado', 'Ngong', 'Kitengela', 'Ongata Rongai'],
    'Kakamega': ['Kakamega', 'Mumias', 'Malava'],
    'Kericho': ['Kericho', 'Litein', 'Kipkelion'],
    'Kiambu': ['Kiambu', 'Thika', 'Ruiru', 'Limuru', 'Kikuyu'],
    'Kilifi': ['Kilifi', 'Malindi', 'Mtwapa'],
    'Kirinyaga': ['Kerugoya', 'Kutus', 'Sagana'],
    'Kisii': ['Kisii', 'Ogembo', 'Suneka'],
    'Kisumu': ['Kisumu', 'Maseno', 'Ahero'],
    'Kitui': ['Kitui', 'Mwingi', 'Mutomo'],
    'Kwale': ['Kwale', 'Ukunda', 'Msambweni'],
    'Laikipia': ['Nanyuki', 'Nyahururu', 'Rumuruti'],
    'Lamu': ['Lamu', 'Mpeketoni', 'Witu'],
    'Machakos': ['Machakos', 'Athi River', 'Kangundo'],
    'Makueni': ['Wote', 'Emali', 'Sultan Hamud'],
    'Mandera': ['Mandera', 'El Wak', 'Rhamu'],
    'Marsabit': ['Marsabit', 'Moyale', 'Loiyangalani'],
    'Meru': ['Meru', 'Nkubu', 'Maua'],
    'Migori': ['Migori', 'Rongo', 'Awendo'],
    'Mombasa': ['Mombasa Island', 'Nyali', 'Likoni', 'Changamwe'],
    "Murang'a": ["Murang'a", 'Kenol', 'Kangema'],
    'Nairobi': ['Nairobi CBD', 'Westlands', 'Embakasi', 'Kasarani', 'Dagoretti'],
    'Nakuru': ['Nakuru', 'Naivasha', 'Molo', 'Gilgil'],
    'Nandi': ['Kapsabet', 'Nandi Hills', 'Mosoriot'],
    'Narok': ['Narok', 'Kilgoris', 'Ololulunga'],
    'Nyamira': ['Nyamira', 'Keroka', 'Nyansiongo'],
    'Nyandarua': ['Ol Kalou', 'Ol Joro Orok', 'Engineer'],
    'Nyeri': ['Nyeri', 'Karatina', 'Othaya'],
    'Samburu': ['Maralal', 'Baragoi', 'Archers Post'],
    'Siaya': ['Siaya', 'Bondo', 'Ugunja'],
    'Taita-Taveta': ['Voi', 'Taveta', 'Mwatate'],
    'Tana River': ['Hola', 'Garsen', 'Bura'],
    'Tharaka-Nithi': ['Chuka', 'Kathwana', 'Marimanti'],
    'Trans Nzoia': ['Kitale', 'Kiminini', 'Endebess'],
    'Turkana': ['Lodwar', 'Kakuma', 'Lokichoggio'],
    'Uasin Gishu': ['Eldoret', 'Turbo', 'Moiben', 'Burnt Forest'],
    'Vihiga': ['Mbale', 'Vihiga', 'Luanda'],
    'Wajir': ['Wajir', 'Habaswein', 'Griftu'],
    'West Pokot': ['Kapenguria', 'Makutano', 'Chepareria'],
}

KENYA_COUNTY_CHOICES = [(county, county) for county in COUNTY_TOWNS]
ALL_TOWN_CHOICES = sorted({(town, town) for towns in COUNTY_TOWNS.values() for town in towns})
