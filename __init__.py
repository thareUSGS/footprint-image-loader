def classFactory(iface):
    from .lift import LiftPlugin
    return LiftPlugin(iface)
