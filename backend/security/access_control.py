"""
Access Control Service - Implement role-based access control (RBAC)
"""
from django.contrib.auth.models import User, Permission, Group
from django.contrib.contenttypes.models import ContentType
from .models import UserSecurityProfile, AuditLog
import logging

logger = logging.getLogger(__name__)


class AccessControlService:
    """Service for managing role-based access control"""
    
    ROLES = {
        'admin': {
            'description': 'Administrator - Full system access',
            'permissions': [
                'add_user', 'change_user', 'delete_user',
                'add_client', 'change_client', 'delete_client',
                'add_application', 'change_application', 'delete_application',
                'add_payment', 'change_payment', 'delete_payment',
                'add_ticket', 'change_ticket', 'delete_ticket',
                'view_audit_logs', 'manage_security_settings'
            ]
        },
        'operator': {
            'description': 'Operator - Manage payments and tickets',
            'permissions': [
                'add_payment', 'change_payment',
                'add_ticket', 'change_ticket',
                'view_audit_logs'
            ]
        },
        'client': {
            'description': 'Client - View own data',
            'permissions': [
                'view_own_applications',
                'view_own_payments',
                'view_own_tickets'
            ]
        },
        'viewer': {
            'description': 'Viewer - Read-only access',
            'permissions': [
                'view_client',
                'view_application',
                'view_payment',
                'view_ticket'
            ]
        }
    }
    
    @staticmethod
    def assign_role(user, role):
        """
        Assign role to user
        
        Args:
            user (User): User to assign role to
            role (str): Role name
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            if role not in AccessControlService.ROLES:
                return {
                    'success': False,
                    'message': f'Invalid role: {role}'
                }
            
            # Get or create group
            group, _ = Group.objects.get_or_create(name=role)
            
            # Add user to group
            user.groups.add(group)
            
            # Update security profile
            security_profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
            security_profile.role = role
            security_profile.save()
            
            # Log audit event
            AuditLog.objects.create(
                action_type='role_change',
                description=f'User role changed to: {role}',
                related_user=user,
                status='success'
            )
            
            logger.info(f'Role assigned: {user.username} -> {role}')
            
            return {
                'success': True,
                'message': f'Role {role} assigned to {user.username}'
            }
            
        except Exception as e:
            logger.error(f'Error assigning role: {str(e)}')
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    @staticmethod
    def get_user_role(user):
        """
        Get user's role
        
        Args:
            user (User): User object
            
        Returns:
            str: Role name or None
        """
        try:
            security_profile = UserSecurityProfile.objects.get(user=user)
            return security_profile.role
        except:
            return None
    
    @staticmethod
    def has_role(user, role):
        """
        Check if user has specific role
        
        Args:
            user (User): User object
            role (str): Role name
            
        Returns:
            bool: True if user has role
        """
        return user.groups.filter(name=role).exists()
    
    @staticmethod
    def has_permission(user, permission):
        """
        Check if user has specific permission
        
        Args:
            user (User): User object
            permission (str): Permission name
            
        Returns:
            bool: True if user has permission
        """
        if user.is_superuser:
            return True
        
        try:
            security_profile = UserSecurityProfile.objects.get(user=user)
            role = security_profile.role
            
            if role in AccessControlService.ROLES:
                role_permissions = AccessControlService.ROLES[role]['permissions']
                return permission in role_permissions
            
            return False
            
        except:
            return False
    
    @staticmethod
    def can_access_resource(user, resource_type, resource_id=None, action='view'):
        """
        Check if user can access specific resource
        
        Args:
            user (User): User object
            resource_type (str): Type of resource (client, application, payment, ticket)
            resource_id: ID of resource
            action (str): Action type (view, edit, delete)
            
        Returns:
            bool: True if user can access resource
        """
        if user.is_superuser:
            return True
        
        try:
            role = AccessControlService.get_user_role(user)
            
            if role == 'admin':
                return True
            
            if role == 'viewer':
                return action == 'view'
            
            if role == 'client':
                # Check if resource belongs to user
                return AccessControlService._is_own_resource(user, resource_type, resource_id)
            
            if role == 'operator':
                # Operators can access most resources except delete
                return action != 'delete'
            
            return False
            
        except Exception as e:
            logger.error(f'Error checking resource access: {str(e)}')
            return False
    
    @staticmethod
    def _is_own_resource(user, resource_type, resource_id):
        """
        Check if resource belongs to user
        
        Args:
            user (User): User object
            resource_type (str): Type of resource
            resource_id: ID of resource
            
        Returns:
            bool: True if resource belongs to user
        """
        try:
            from api.models import Application
            
            if resource_type == 'application':
                app = Application.objects.get(app_id=resource_id)
                return app.user == user
            
            # Add more resource type checks as needed
            
            return False
            
        except:
            return False
    
    @staticmethod
    def create_custom_role(role_name, description, permissions):
        """
        Create custom role with specified permissions
        
        Args:
            role_name (str): Name of role
            description (str): Role description
            permissions (list): List of permission names
            
        Returns:
            dict: {'success': bool, 'message': str, 'group': Group or None}
        """
        try:
            # Create group
            group, created = Group.objects.get_or_create(name=role_name)
            
            if created:
                logger.info(f'Custom role created: {role_name}')
            
            # Add permissions to group
            for perm_name in permissions:
                try:
                    permission = Permission.objects.get(codename=perm_name)
                    group.permissions.add(permission)
                except Permission.DoesNotExist:
                    logger.warning(f'Permission not found: {perm_name}')
            
            # Store in ROLES dict
            AccessControlService.ROLES[role_name] = {
                'description': description,
                'permissions': permissions
            }
            
            return {
                'success': True,
                'message': f'Role {role_name} created successfully',
                'group': group
            }
            
        except Exception as e:
            logger.error(f'Error creating custom role: {str(e)}')
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'group': None
            }
    
    @staticmethod
    def get_role_permissions(role):
        """
        Get all permissions for a role
        
        Args:
            role (str): Role name
            
        Returns:
            list: List of permissions
        """
        if role in AccessControlService.ROLES:
            return AccessControlService.ROLES[role]['permissions']
        
        try:
            group = Group.objects.get(name=role)
            return [perm.codename for perm in group.permissions.all()]
        except:
            return []
    
    @staticmethod
    def remove_role(user, role):
        """
        Remove role from user
        
        Args:
            user (User): User object
            role (str): Role name
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            group = Group.objects.get(name=role)
            user.groups.remove(group)
            
            AuditLog.objects.create(
                action_type='role_change',
                description=f'Role removed: {role}',
                related_user=user,
                status='success'
            )
            
            return {
                'success': True,
                'message': f'Role {role} removed from {user.username}'
            }
            
        except Exception as e:
            logger.error(f'Error removing role: {str(e)}')
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    @staticmethod
    def get_users_by_role(role):
        """
        Get all users with specific role
        
        Args:
            role (str): Role name
            
        Returns:
            QuerySet: Users with specified role
        """
        try:
            group = Group.objects.get(name=role)
            return group.user_set.all()
        except:
            return User.objects.none()
    
    @staticmethod
    def audit_permission_denied(user, resource_type, resource_id, action):
        """
        Log permission denied event
        
        Args:
            user (User): User attempting access
            resource_type (str): Type of resource
            resource_id: ID of resource
            action (str): Attempted action
        """
        try:
            AuditLog.objects.create(
                user=user,
                action_type='permission_change',
                description=f'Access denied: {action} on {resource_type} #{resource_id}',
                status='failed'
            )
            
            logger.warning(f'Permission denied: {user.username} tried to {action} {resource_type} #{resource_id}')
            
        except Exception as e:
            logger.error(f'Error auditing permission denial: {str(e)}')
