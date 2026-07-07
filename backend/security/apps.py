from django.apps import AppConfig


class SecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'security'
    verbose_name = 'Security & Authentication'
    
    def ready(self):
        """
        Initialize security app when Django starts
        """
        import logging
        logger = logging.getLogger('security')
        logger.info('Security module loaded')
        
        # Import signals if needed
        try:
            from . import signals
        except ImportError:
            pass
