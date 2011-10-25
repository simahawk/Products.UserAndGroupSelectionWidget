import types
import operator
from zope.interface import implements
from Products.Five import BrowserView
from Products.PlonePAS.interfaces.group import IGroupIntrospection
from ZTUtils import make_query
from Products.CMFCore.utils import getToolByName
from interfaces import IUserAndGroupSelectView
from interfaces import IUserAndGroupSelectPopupView
from memberlookup import MemberLookup
from memberlookup import get_user_display_name
from alphabatch import AlphaBatch


class UserAndGroupSelectView(BrowserView):
    """See interfaces.IUserAndGroupSelectView for documentation details.
    """

    def getUserOrGroupTitle(self, id):

        # handle users
        pm = getToolByName(self.context, 'portal_membership')
        # acl_user user object behave differently w/ 'hasProperty' check
        user = pm.getMemberById(id)
        if user is not None:
            return get_user_display_name(user)

        # handle groups
        pas = getToolByName(self.context, 'acl_users')
        for pluginid, plugin in pas.plugins.listPlugins(IGroupIntrospection):
            group = plugin.getGroupById(id)
            if group is not None:
                title = self._getPropertyForGroup(group, 'title')
                return title or id

        return id

    def _getPropertyForGroup(self, group, propertyname):
        propsheets = group.listPropertysheets()
        for propsheettitle in propsheets:
            propsheet = group.getPropertysheet(propsheettitle)
            property = propsheet.getProperty(propertyname, None)
            if property:
                return property
        return None


class UserAndGroupSelectPopupView(BrowserView):
    """See interfaces.IUserAndGroupSelectPopupView for documentation details.
    """

    implements(IUserAndGroupSelectView)

    def initialize(self):
        """Initialize the view class.
        """
        schema = self.context.Schema()
        fieldId = self.request['fieldId']

        # compoundfield and arrayfield compatibility
        field = self.context
        fieldIds = fieldId.split('-')
        for fieldId in fieldIds:
            field = field.Schema().getField(fieldId)

        self.multivalued = field.multiValued
        self.widget = field.widget
        self.memberlookup = MemberLookup(self.context,
                                         self.request,
                                         self.widget)

    def getObjectUrl(self):
        r = '%s/%s' % (self.context.absolute_url(), 'userandgroupselect_popup')
        return r

    def getQueryUrl(self, **kwargs):
        baseUrl = self.context.absolute_url()
        if self.request.get('fieldId', '') != '':
            baseUrl += '/userandgroupselect_popup'
        query = self._getQueryString(**kwargs)
        url = '%s?%s' % (baseUrl, query)
        return url

    def isSelected(self, param, value):
        param = self.request.get(param)
        if param:
            if param is types.StringType:
                param = [param]
            if value in param:
                return True
        return False

    def getGroupsForPulldown(self):
        ret = [('ignore', '-')]
        groups = self.memberlookup.getGroups()
        return ret + sorted(groups, key=operator.itemgetter(1))

    def getBatch(self):
        members = self.memberlookup.getMembers()
        return AlphaBatch(members, self.context, self.request)

    def usersOnly(self):
        return self.widget.usersOnly

    def groupsOnly(self):
        return self.widget.groupsOnly

    def multiValued(self):
        if self.multivalued:
            return 1
        return 0

    def _getQueryString(self, **kwargs):
        params = dict()
        for key in self.request.form.keys():
            params[key] = self.request.form[key]
        params.update(kwargs)
        query = make_query(params)
        return query
