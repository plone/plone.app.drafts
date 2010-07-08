import zope.component
from zope.interface import alsoProvides

from Acquisition.interfaces import IAcquirer
from Acquisition import aq_inner

from plone.app.drafts.utils import syncDraft
from plone.app.drafts.utils import getCurrentDraft
 
from plone.dexterity.interfaces import IDexterityContainer, IDexterityItem
from plone.dexterity.interfaces import IDexterityFTI
from plone.dexterity.utils import createContent

from plone.app.drafts.interfaces import IDexterityDraft
from plone.app.drafts.interfaces import IDexterityDraftAdding
from plone.app.drafts.interfaces import IDexterityDraftEditing

# TODO this should not be here; should be in behaviors
from plone.app.dexterity.behaviors.drafts import IDexterityDraftSubmitBehavior
from plone.app.dexterity.behaviors.drafts import IDexterityDraftCancelBehavior
from plone.app.drafts.interfaces import IDexterityDraftContainer
from plone.app.drafts.interfaces import IDexterityDraftItem
#from experimental.dexterityz3cformdrafts.drafts import setupDraft


# NOT YET USED
class DexterityDraftError( Exception ):
    """
    """
    pass

def addBegun(form, event):
    fti = zope.component.queryUtility( IDexterityFTI, name=form.portal_type )
    if not 'plone.app.drafts.interfaces.IDexterityDraftable' in fti.behaviors:
        return

##    form.context = getDraftContext( form.context, form.request, form.portal_type, view_name='add' )
##    
##    if IDexterityDraft.providedBy(form.context):
##        form.ignoreContext = False
        
    #draftRequestForm(form, event)
    return

def editBegun(form, event):
    fti = zope.component.queryUtility( IDexterityFTI, name=form.portal_type )
    if not 'plone.app.drafts.interfaces.IDexterityDraftable' in fti.behaviors:
        return
    
##    form.context = getDraftContext( form.context, form.request, form.portal_type, view_name='edit' )
    
    draftRequestForm(form, event)

################################################################################

def getDraftContext(context, request, portal_type, view_name=None):
    """Returns a dexterity draft object if the behavior IDexterityDraftable is
       set; otherwise will return original context.  If a draft does not already
       exist, one will be created"""
    
    fti = zope.component.queryUtility( IDexterityFTI, name=portal_type )
    if not 'plone.app.drafts.interfaces.IDexterityDraftable' in fti.behaviors:
        return context
        
    context = aq_inner( context ) # New
    setupDraft( context, request, None )
    
    #request = getattr(context, 'REQUEST', None)
    if request is None:
        return context
    
    draft = getCurrentDraft(request)
    if draft is None:
        # Don't allow a draft to be created if view_name is None
        # It should be 'add' or 'edit'
        if view_name is None:
            return context

        new_context = createDraftContext( context, portal_type, view_name )
        if new_context is None:
            return context
    else:
        new_context = getattr( draft, 'context', None )
        
    if new_context is None:
        return context

    if IAcquirer.providedBy(new_context):
        new_context = new_context.__of__( context )
    
    return new_context

def createDraftContext(context, portal_type, view_name):
    context = aq_inner(context) #NEW
    request = getattr(context, 'REQUEST', None)
    if request is None:
        return None
    
    draft = getCurrentDraft(request, create=True)
    if draft is None:
        return None
    
    new_context = createContent( portal_type )
    
    alsoProvides( new_context, IDexterityDraft )
    alsoProvides( new_context, IDexterityDraftSubmitBehavior )
    alsoProvides( new_context, IDexterityDraftCancelBehavior )
    
    if IDexterityContainer.providedBy( new_context ):
        alsoProvides( new_context, IDexterityDraftContainer )
    elif IDexterityItem.providedBy( new_context ):
        alsoProvides( new_context, IDexterityDraftItem )

    if view_name == 'add':
        alsoProvides( new_context, IDexterityDraftAdding )
    elif view_name == 'edit':
        alsoProvides( new_context, IDexterityDraftEditing )
        
    new_context.id = '++%s_draft++%s' % (view_name, portal_type)
    new_context.__parent__ = aq_inner( context )
    setattr( draft, 'context', new_context )
    
    if IDexterityDraftEditing.providedBy( new_context ):
        # sync the draft up via data from original context
        syncDraft(context, new_context)
    
    return new_context

################################################################################

def draftRequestForm(form, event):

    fti = zope.component.queryUtility( IDexterityFTI, name=form.portal_type )
    if not 'plone.app.drafts.interfaces.IDexterityDraftable' in fti.behaviors:
        return context
        
    request = getattr(form.context, 'REQUEST', None)
    if request is None:
        return
    
    setupDraft( form.context, request, event )
    
    draft = getCurrentDraft(request, create=True)
    if draft is None:
        return
    
    draft_request_form = getattr( draft, '_form', {} ).copy()
    
    # TEMP (REMOVE ANY button actions from draft
    for key, value in draft_request_form.items():
        if key.startswith( 'form.buttons' ):
            draft_request_form.pop( key )
            
        
    from zope.schema import getFields
    from ZPublisher.HTTPRequest import FileUpload
    from z3c.form import interfaces
    
    fields = getFields( fti.lookupSchema() )
    for key, value in request.form.items():
        # Don't save button actions
        if key.startswith( 'form.buttons' ):
            continue
        
##        if draft_request_form.get(key+'.prevent_override', None):
##            # Dont save the form value (used for ajax widgets)
##            if not request.form.has_key( value + '.override' ):
##                continue 
        
        # Save the converted value in draft object since some may be 
        # instancemethod objects (FileUpload is ) which can not be pickled
        field = fields.get(key[key.rfind('.')+1:], None)
        if field is not None:
            #widget = zope.component.getMultiAdapter( (field, request), interfaces.IFieldWidget )            
            #extracted_value = widget.extract(value)
            #converted_value = interfaces.IDataConverter(widget).toFieldValue( value )
            #converted_value = interfaces.IDataConverter(widget).toWidgetValue( value )
            
            # TODO:  check to see if value is instancemethod
            
            # Don't overwite blank FileUpload fields
            if isinstance(value, FileUpload):
                widget = zope.component.getMultiAdapter( (field, request), interfaces.IFieldWidget )            
                converted_value = interfaces.IDataConverter(widget).toFieldValue( value )
                
                if converted_value is None: 
                    if draft_request_form.has_key( key ):
                        draft_value = draft_request_form.get(key)
                        if draft_value is not None:
                            continue
                        
                value = converted_value #This may be enough to update request.form?
            
        draft_request_form[key] = value
        
        #DEBUG; test only to see if this will work for preview
        # (set attribute directly; not just on form)
        # if this works; dont set anything not in schema
        #setattr( draft, key[13:], value )
        
    # Re-wrtie the form from draft incase anything was changed since last request
    setattr( draft, '_form', draft_request_form )
    form.context.REQUEST.form = draft_request_form.copy()
    form.request.form = form.context.REQUEST.form #may not need this; same object?
    
    return

################################################################################

from zope.component import queryUtility

from plone.app.drafts.interfaces import IDraftStorage
from plone.app.drafts.interfaces import ICurrentDraftManagement
from plone.app.drafts.archetypes import getArchetypesObjectKey


# Helper methods
def setupDraft(context, request=None, event=None):
    """When we enter the edit screen, set up the target key and draft cookie
    path. If there is exactly one draft for the given user id and target key,
    consider that to be the current draft. Also mark the request with
    IDrafting if applicable.
    """
    if request is None:
        return None
    
    storage = queryUtility(IDraftStorage)
    if storage is None or not storage.enabled:
        return None
    
    current = ICurrentDraftManagement(request)
    
    # Update target key regardless - we could have a stale cookie
    current.targetKey = getArchetypesObjectKey(context)
    
    if current.userId is None:
        # More than likely user has not yet been validated, so try to figure 
        # it out
        plone_site = context.unrestrictedTraverse( '/'+context.getPhysicalPath()[1] )
        plone_pluggable_auth_service = plone_site.__allow_groups__
        plugins = plone_site.__allow_groups__._getOb('plugins')
        user_ids = plone_pluggable_auth_service._extractUserIds( request, plugins )

        if len(user_ids) == 0:
            root = context.unrestrictedTraverse('/')
            root_pluggable_auth_service = root.__allow_groups__
            plugins = root.__allow_groups__._getOb('plugins')
            user_ids = root_pluggable_auth_service._extractUserIds( request, plugins )
        
        if len(user_ids) == 0:
            return None

        user_id, login = user_ids[0]
        current.userId = user_id
        
    if current.userId is None:
        return None
        
    if current.draftName is None:
        drafts = storage.getDrafts(current.userId, current.targetKey)
        if len(drafts) == 1:
            current.draftName = tuple(drafts.keys())[0]
    
    # Save the path now so that we can use it again later, even on URLs 
    # (e.g. in AJAX dialogues) that are below this path.
    current.path = current.defaultPath
    
    # Mark context with IDraft
    current.mark()
    current.save()
    
    return current

################################################################################

import zope.schema.interfaces
import zope.lifecycleevent
import zope.event

from zope.interface import implements
from zope.component import adapts
from zope.component import queryUtility
from zope.schema import getFields

from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.interfaces import IDexterityFTI
 
from plone.app.drafts.interfaces import IDraft, IDraftSyncer

from plone.app.drafts.interfaces import IDexterityDraft

class NotFound(object):
    """
    """

class PopulateContentFromDraftSyncer(object):
    """Copy draft persistent dexterity data to the
    real object on save, or vise versa.  This syncer
    is customized to only populate the draft.context
    content object
    """

    implements(IDraftSyncer)
    adapts(IDraft, IDexterityContent)

    # notify of object changes
    notify = True
    
    def __init__(self, source, target):
        self.source = source.context
        self.target = target

    def __call__(self):
        changes = {}
        
        fti = queryUtility(IDexterityFTI, self.target.portal_type)
        schema = getFields( fti.lookupSchema() )
        
        for field_name, field_schema in schema.items():
            source_attr = getattr( self.source, field_name, NotFound )
            if source_attr is not NotFound:
                target_attr = getattr( self.target, field_name, NotFound )
                if target_attr is not NotFound:
                    if (source_attr != target_attr 
                        or zope.schema.interfaces.IObject.providedBy(field_schema)):
                        setattr( self.target, field_name, getattr(self.source, field_name) )
                        
                        # Record the change using information required later
                        changes.setdefault(field_schema.interface, []).append(field_name)

        if self.notify:
            if changes:
                descriptions = []
                for interface, names in changes.items():
                    descriptions.append(
                        zope.lifecycleevent.Attributes(interface, *names))
                    
                # Send out a detailed object-modified event
                zope.event.notify(
                    zope.lifecycleevent.ObjectModifiedEvent(self.target,
                        *descriptions))

        return changes

class PopulateDraftFromContextSyncer(PopulateContentFromDraftSyncer):
    implements(IDraftSyncer)
    adapts(IDexterityContent, IDexterityDraft)
    
    def __init__(self, source, target):
        self.source = source
        self.target = target
        self.notify = False
        
