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
