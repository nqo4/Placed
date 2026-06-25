from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from .models import Place

@registry.register_document
class PlaceDocument(Document):
    class Index:
        name = 'places'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    name = fields.TextField()
    description = fields.TextField()
    address = fields.TextField()

    class Django:
        model = Place
        fields = [
            'id',
            'created_at',
            'image_url',
        ]