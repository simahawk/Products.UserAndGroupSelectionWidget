import time
import types
from zope.component import ComponentLookupError

from Products.CMFCore.utils import getToolByName
from Products.PlonePAS.interfaces.group import IGroupIntrospection

from bda.cache import ICacheManager
from bda.cache import Memcached

from interfaces import IGenericGroupTranslation
from interfaces import IGenericFilterTranslation

# make this dynamic, XXX
CACHEPROVIDER = Memcached(['127.0.0.1:11211'])

def get_user_display_name(user):
    """ given a user returns its name for listing
    """
    name = ""
    if user.hasProperty('fullname'):
        name = user.getProperty('fullname')
    if not name:
        # weird: Membrane user don't have
        # fullname property properly set
        name = user.getProperty('title')
    return name or user.getId()


class MemberLookup(object):
    """This object contains the logic to list and search for users and groups.
    """

    def __init__(self, context, request, widget):
        """Construct this object and do base initialization.
        """
        self.context = context
        self.widget = widget
        self.searchabletext = request.get('searchabletext', '')
        group = request.get('selectgroup', '')
        try:
            grouptranslation = IGenericGroupTranslation(self.context)
            self.currentgroupid = grouptranslation.translateToRealGroupId(group)
        except ComponentLookupError:
            self.currentgroupid = group
        except TypeError, e:
            if e[0] == 'Could not adapt':
                self.currentgroupid = group
            else:
                raise
        return

    def getGroups(self):
        """Return the groups.
        """
        #start = time.time()
        filter = self._allocateFilter()
        aclu = getToolByName(self.context, 'acl_users')
        groups = aclu.getGroups()
        ret = []
        for group in groups:
            gid = group.getId()
            if not self._groupIdFilterMatch(gid, filter):
                continue
            ret.append((gid, group.getGroupTitleOrName()))
        #print 'getGroups took %s' % str(time.time() - start)
        return ret

    def getMembers(self):
        """Return the Users in the following form.

        {
            'id': 'mmustermann',
            'fullname': 'Max Mustermann',
        }
        """
        #start = time.time()
        filter = self._allocateFilter()
        group = self.currentgroupid
        if group != 'ignore' and group != '':
            key = 'userandgroupselectionwidget:%s' % group
            manager = ICacheManager(CACHEPROVIDER)
            users = manager.getData(self._readGroupMembers, key, args=[group])
        else:
            users = self._searchUsers()
        reduce = True
        for fil in filter:
            if fil == '*':
                reduce == False
        if reduce:
            users = self._reduceMembers(users, filter)
        return users

    def _getUserIdsOfGroup(self, groupid):
        aclu = getToolByName(self.context, 'acl_users')
        for id, giplugin in aclu.plugins.listPlugins(IGroupIntrospection):
            userids = giplugin.getGroupMembers(groupid)
            if userids:
                return userids
        return []

    def _readGroupMembers(self, gid):
        aclu = getToolByName(self.context, 'acl_users')
        user_ids = self._getUserIdsOfGroup(gid)
        return self._getUserDefs(user_ids)

    def _searchUsers(self):
        st = self.searchabletext
        # TODO: Search is done over all available groups, not only over groups
        # which should be applied. also see getGroups.
        if len(st) < 3:
            return []
        aclu = getToolByName(self.context, 'acl_users')
        users_dict = aclu.searchUsers(name=st)
        user_ids = [user['id'] for user in users_dict]
        return self._getUserDefs(user_ids)

    def _getUserDefs(self, uids):
        pm = getToolByName(self.context, 'portal_membership')
        users = [pm.getMemberById(user_id) for user_id in uids]
        ret = []
        for user in users:
            if user is None:
                continue
            entry = {
                'id': user.getId(),
                'fullname': get_user_display_name(user),
            }
            ret.append(entry)
        ret.sort(cmp=lambda x, y: \
            x['fullname'].lower() > y['fullname'].lower() and 1 or -1)
        return ret

    def _allocateFilter(self):
        filter = self.widget.groupIdFilter
        try:
            filtertranslation = IGenericFilterTranslation(self.context)
            filter = filtertranslation.translateToFilterDefinition(filter)
        except ComponentLookupError:
            pass
        except TypeError, e:
            if e[0] == 'Could not adapt':
                pass
            else:
                raise
        if type(filter) in types.StringTypes:
            filter = [filter,]
        return filter

    def _groupIdFilterMatch(self, gid, filter):
        """Check if gid matches filter.
        """
        for fil in filter:
            # wildcard match
            if fil.find('*') != -1:
                # all groups are affected
                if fil == '*':
                    return True
                # wildcard matches like '*foo'
                elif fil.startswith('*'):
                    if gid.endswith(fil[1:]):
                        return True
                # wildcard matches like 'foo*'
                elif fil.endswith('*'):
                    if gid.startswith(fil[:-1]):
                        return True
                # wildacard matches like '*foo*'
                else:
                    if gid.find(fil[1:-1]) != -1:
                        return True
            # exact match
            else:
                if fil == gid:
                    return True
        return False

    def _reduceMembers(self, members, filter):
        """Reduce members to match filter.
        """
        # TODO
        return members