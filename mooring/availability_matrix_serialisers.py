from rest_framework import serializers


class MooringsiteTreeSerialiser(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    is_open = serializers.SerializerMethodField()

    def get_is_open(self, obj):
        return obj.active


class MooringAreaTreeSerialiser(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    is_open = serializers.SerializerMethodField()
    sites = serializers.SerializerMethodField()

    def get_is_open(self, obj):
        return obj.active

    def get_sites(self, obj):
        # obj.campsites is prefetched by the view, .all() reuses the cache without extra queries
        return MooringsiteTreeSerialiser(obj.campsites.all(), many=True).data


class AvailabilityCellSerialiser(serializers.Serializer):
    site_id = serializers.IntegerField()
    date = serializers.DateField()
    status = serializers.CharField()
    rate = serializers.CharField(allow_null=True)


class RateDetailSerialiser(serializers.Serializer):
    price_model = serializers.CharField()
    rate_type = serializers.CharField()
    mooring = serializers.CharField()
    adult = serializers.CharField(allow_null=True)
    concession = serializers.CharField(allow_null=True)
    child = serializers.CharField(allow_null=True)
    infant = serializers.CharField(allow_null=True)
    reason = serializers.CharField(allow_null=True)
    details = serializers.CharField(allow_null=True)


class BookingPeriodDetailSerialiser(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    start_time = serializers.TimeField(allow_null=True)
    finish_time = serializers.TimeField(allow_null=True)
    small_price = serializers.CharField(allow_null=True)
    medium_price = serializers.CharField(allow_null=True)
    large_price = serializers.CharField(allow_null=True)
    status = serializers.CharField()


class ExistingBookingSerialiser(serializers.Serializer):
    id = serializers.IntegerField()
    booking_type = serializers.CharField()
    from_dt = serializers.DateTimeField(allow_null=True)
    to_dt = serializers.DateTimeField(allow_null=True)


class CellDetailSerialiser(serializers.Serializer):
    site_id = serializers.IntegerField()
    site_name = serializers.CharField()
    mooringarea_name = serializers.CharField()
    date = serializers.DateField()
    status = serializers.CharField()
    rate = RateDetailSerialiser(allow_null=True)
    booking_periods = BookingPeriodDetailSerialiser(many=True)
    bookings = ExistingBookingSerialiser(many=True)

