from django.core.management.base import BaseCommand
import pandas as pd
import numpy as np
from mooring.models import MooringArea, MarinePark, MooringAreaGroup
from confy import env

COLUMN_MAPPINGS = {
    "Mooring Name": "name",
    "Mooring Park": "park",
    "Mooring Physical Type": "physical_type",
    "Mooring Class": "class",
    "Maximum Vessel Size (Metres)": "vessel_size",
    "Maximum Vessel Draft (Metres)": "vessel_draft",
    "Maximum Vessel Weight (Tonnes)": "vessel_weight",
}

MOORING_PHYSICAL_TYPE_CHOICES = {
    'Mooring': 0,
    'Jetty Pen': 1,
    'Beach Pen': 2,
}

MOORING_CLASS_CHOICES = {
    'Small': 'small',
    'Medium': 'medium',
    'Large': 'large',
}

class Command(BaseCommand):
    help = 'Import private moorings from file.\n'\
    'python manage_mo.py import_private_moorings --path tmp/moorings.csv'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str)

    def handle(self, *args, **options):

        filepath = options['path']
        if not filepath:
            filepath = env('IMPORT_MOORINGS_PATH', 'tmp/moorings.csv')

        try:
            data=pd.read_csv(filepath, delimiter=',', dtype=str)
        except Exception as e:
            print(e)
            return

        data = data.rename(columns=COLUMN_MAPPINGS)
        data[data.columns] = data.apply(lambda x: x.str.strip() if isinstance(x, str) else x)
        data.fillna('', inplace=True)
        data.replace({np.nan: ''}, inplace=True)

        errors = []
        new = []
        #updated = []
        exists = []

        for index, row in data.iterrows():
            try:
                
                mooring_class = MOORING_CLASS_CHOICES[row["class"]] if row["class"] else 0

                #vessel weight limit is optional, size and draft limits are not
                vessel_weight = float(row["vessel_weight"]) if row["vessel_weight"] else 0
                if not row["vessel_size"]:
                    errors.append("Vessel size limit not provided")
                    continue
                if not row["vessel_draft"]:
                    errors.append("Vessel draft limit not provided")
                    continue

                parks_qs = MarinePark.objects.filter(name=row["park"])
                if not parks_qs.exists():
                    errors.append("Park {} does not exists".format(row["park"]))
                    continue
                else:
                    park = parks_qs.first()                

                moorings_qs = MooringArea.objects.filter(name=row["name"])
                if moorings_qs.exists():
                    #update
                    #NOTE refrain from updating (could make this an option)
                    #mooring_area = moorings_qs.first()
                    #mooring_area.name = row["name"]
                    #mooring_area.park = park
                    #mooring_area.mooring_physical_type = MOORING_PHYSICAL_TYPE_CHOICES[row["physical_type"]]
                    #mooring_area.mooring_class = mooring_class
                    #mooring_area.vessel_size_limit = float(row["vessel_size"])
                    #mooring_area.vessel_draft_limit = float(row["vessel_draft"])
                    #mooring_area.vessel_weight_limit = vessel_weight
                    #mooring_area.save()
                    #updated.append(row["name"])
                    exists.append(row["name"])
                else:
                    #create
                    MooringArea.objects.create(
                        mooring_specification = 2,
                        mooring_type = 1,
                        name = row["name"],
                        park = park,
                        mooring_physical_type = MOORING_PHYSICAL_TYPE_CHOICES[row["physical_type"]],
                        mooring_class = mooring_class,
                        vessel_size_limit = float(row["vessel_size"]),
                        vessel_draft_limit = float(row["vessel_draft"]),
                        vessel_weight_limit = vessel_weight,
                    )
                    new.append(row["name"])
            except Exception as e:
                errors.append(str(index) + " " + str(e))

        print("New moorings added",len(new))
        print("Mooring aleady exists", len(exists))

        if errors:
            print("\nErrors\n")
            for i in errors:
                print(i)