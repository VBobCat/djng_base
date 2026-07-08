from drf_spectacular.openapi import AutoSchema


class CustomAutoSchema(AutoSchema):
    def get_tags(self):
        fragments = [f for f in self.path.strip('/').split('/') if f]
        if len(fragments) >= 3:
            tag = f'{fragments[1]}: {fragments[2]}'
            return [tag.replace('_', ' ').title()]

        return [tag.title() for tag in super().get_tags()]