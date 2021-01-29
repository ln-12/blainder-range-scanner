class HitInfo:
    def __init__(self, location, faceNormal, faceIndex, distance, target):
        self.location = location
        self.faceNormal = faceNormal
        self.faceIndex = faceIndex
        self.distance = distance
        self.target = target
        self.color = None
        self.intensity = None

        self.noiseLocation = None
        self.noiseDistance = None

        self.wasReflected = False

        self.x = None
        self.y = None

        self.partID = None
        self.categoryID = None