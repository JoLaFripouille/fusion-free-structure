"""Masque uniquement l’occurrence remplacée pendant un aperçu."""


class PreviewVisibility:
    def __init__(self):
        self.hidden = None

    def hide(self, occurrence):
        self.restore()
        if occurrence and occurrence.isValid and occurrence.isLightBulbOn:
            self.hidden = occurrence
            occurrence.isLightBulbOn = False

    def restore(self):
        occurrence, self.hidden = self.hidden, None
        if occurrence and occurrence.isValid:
            occurrence.isLightBulbOn = True
