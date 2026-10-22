def classFactory(iface):
    from .footprint_image_loader import FootprintImageLoader
    return FootprintImageLoader(iface)
