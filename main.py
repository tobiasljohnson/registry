import time
import logging
from functools import wraps

from google.appengine.ext import ndb
import webapp2
Route = webapp2.Route
from webapp2_extras import auth, sessions, routes, jinja2, json
from webapp2_extras.routes import RedirectRoute, PathPrefixRoute
from webapp2_extras.auth import InvalidAuthIdError, InvalidPasswordError

from models import RegistryUser, Registry, RegistryEntry, Claim


def builder_login_required(f):
    """
    Decorator that checks if there's a user associated with the current session.
    Will also fail if there's no session present.
    """
    def check_login(self, *args, **kwargs):
        user = self.auth.get_user_by_session()
        if not user or user.get('owner_tuple') is not None:
            return self.redirect_to('builder-login')
        else:
            return f(self, *args, **kwargs)

    return check_login

def get_registry_from_name(f):
    """Replace registry_name with registry or abort with a 404.

    Take a function of form f(self, registry, ...) and return one of the form
    f(self, registry_name, ...).

    """
    @wraps(f)
    def with_registry_name(self, registry_name, *args, **kwargs):
        registry = Registry.get_by_name(registry_name)
        logging.info(str(registry))
        if not registry:
            logging.info(str(registry))
            webapp2.abort(404)
        return f(self, registry, *args, **kwargs)
    return with_registry_name

class BaseHandler(webapp2.RequestHandler):
    @webapp2.cached_property
    def jinja2(self):
        """Shortcut to access the jinja2 instance as a property."""
        return jinja2.get_jinja2(app=self.app)
  
    @webapp2.cached_property
    def auth(self):
        """Shortcut to access the auth instance as a property."""
        return auth.get_auth()

    @property
    def user_info(self):
        """Shortcut to access a subset of the user attributes that are stored
        in the session.

        The list of attributes to store in the session is specified in
        config['webapp2_extras.auth']['user_attributes']. The auth_id is also
        stored in the dict under the key 'user_id'.

        """
        return self.auth.get_user_by_session()

    def get_user(self):
        """Shortcut to access the current logged in user.

        Unlike user_info, it fetches information from the persistence layer and
        returns an instance of the underlying model.
        
        """
        u = self.user_info
        if u:
            return ndb.Key(flat=u['user_id']).get()
        else:
            return None

    @webapp2.cached_property
    def user_model(self):
        """Returns the implementation of the user model.

        It is consistent with config['webapp2_extras.auth']['user_model'], if set.
        
        """    
        return self.auth.store.user_model

    @webapp2.cached_property
    def session(self):
        """Shortcut to access the current session."""
        return self.session_store.get_session(backend="datastore")

    def _make_registry_token(self, registry):
        """Create a token authorizing the current (anonymous) user to view registry.

        Store the token in the current session, as a cookie to be deleted on browser close.
        Return the token. Also clears any current such authorization token.

        This function is used internally. See authorize_registry_view and registry_view_authorized.

        """
        self._clear_registry_token()
        self.session['cur_view'] = registry.key.flat()
        token = RegistryUser.create_auth_token(("RegistryUser", "anonymous_user"))
        token_ts = int(time.time())
        self.session['cur_view_token'] = token
        self.session['cur_view_token_ts'] = token_ts
        return token

    def _clear_registry_token(self):
        """Clear the anonymous view token in the current session.

        Delete the token from the session and from the datastore. Take no action if
        there is no anonymous view token in the session.

        This function is used internally. See authorize_registry_view, registry_view_authorized,
        and unauthorize_registry_view.
        """
        if 'cur_view' in self.session:
            token = self.session.get('cur_view_token')
            if not token:
                logging.warning("Tried to clear a non-existent token for {}."
                                .format(str(self.session['cur_view'])))
            RegistryUser.delete_auth_token(("RegistryUser", "anonymous_user"), token)
            self.session.pop('cur_view', None)
            self.session.pop('cur_view_token', None)
            self.session.pop('cur_view_ts', None)
            
    def unauthorize_registry_view(self):
        """Unauthorize the current, anonymous user from viewing any registry."""
        
        self._clear_registry_token()

    def authorize_registry_view(self, registry, password):
        """Authorize the current user to view registry anonymously.

        The authorization will be stored as a cookie until the browser clears it on close.
        Also logs out of any builder account or registry viewer account.
        Return True if the user is successfully authorized, false if the password doesn't match.

        """
        self._clear_registry_token()
        self.auth.unset_session()
        if registry.insecure_password == password:
            logging.info("passwords matched")
            self._make_registry_token(registry)
            return True
        logging.info(password + " didn't match")
        return False

    def registry_view_authorized(self, registry):
        """Return a key to the current user if he/she is authorized to view registry,
        or 'anonymous_user', or False if not authorized."""
        
        if self.user_info: 
            logging.info("checking login credentials")
            owner_tuple = self.user_info.get('owner_tuple')
            logging.info(str(owner_tuple))
            if owner_tuple is None and self.user_info.get('email') == registry.owner.id():
                return ndb.Key(flat=self.user_info['user_id']) #logged on as builder of registry
            if owner_tuple and ndb.Key(flat=owner_tuple) == registry.key:
                return ndb.Key(flat=self.user_info['user_id'])  #logged in as viewer of registry

        # now see if user has a valid anonymous session going
        if self.session.get('cur_view') != registry.key.flat():
            return False
        token = self.session.get('cur_view_token')
        if token:
            token_ts = self.session.get('cur_view_token_ts')
            user, new_token = self.auth.store.validate_token(("RegistryUser", "anonymous_user"),
                                                             token, token_ts)
            if user:
                if not new_token: # user authorized, but token has been cleared to be renewed
                    del self.session['cur_view']
                    self._make_registry_session(registry)
                return 'anonymous_user'
        return False

    def render_template(self, template_filename, params=None):
        """Render a template using jinja2.

        The template gets all parameters in params, plus a parameter 'user_info'
        that it gets from self.user_info. If no user is logged in, this will
        be None.

        """
        if not params:
            params = {}
        params['user_info'] = self.user_info
        rv = self.jinja2.render_template(template_filename, **params)
        self.response.out.write(rv)

    # this is needed for webapp2 sessions to work
    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)
        try:
            webapp2.RequestHandler.dispatch(self)
        finally:
            self.session_store.save_sessions(self.response)

class MainPage(BaseHandler):
    def get(self):
        users = RegistryUser.query().fetch()
        registries = [Registry.query(Registry.owner == user.key) for user in users]
        self.render_template("index.html", {'users_registries': zip(users, registries)})

class BuilderLoginPage(BaseHandler):
    def get(self):
        self.render_template('builder_login.html')

    def post(self):
        email = self.request.get('email')
        password = self.request.get('password')
        try:
            self.auth.get_user_by_password(('RegistryUser', email), password, remember=True,
                                           save_session=True)
            return self.redirect_to('builder-account')
        except (InvalidAuthIdError, InvalidPasswordError) as e:
            logging.info('Login failed for user %s because of %s', email, type(e))
            return self.redirect_to('builder-login', failed=True)

class BuilderLogoutPage(BaseHandler):
    def get(self):
        if self.user_info and self.user_info.get('owner_tuple') is None:
            self.auth.unset_session()
        return self.redirect_to('home')
            
        

class BuilderSignupPage(BaseHandler):
    def get(self):
        self.render_template('signup.html')

    def post(self):
        email = self.request.get('email')
        password = self.request.get('password')

        user = RegistryUser.create(email, password_raw=password)
        if not user:
            return self.redirect_to('builder-signup', invalid_email=email)
        
        self.auth.set_session(self.auth.store.user_to_dict(user), remember=True)
        return self.redirect_to('builder-account')

class BuilderAccountPage(BaseHandler):
    @builder_login_required
    def get(self):
        key = ndb.Key(flat=self.user_info['user_id'])
        registries = Registry.query(Registry.owner == key).fetch()
        new_registry_name = self.request.get('new_registry')
        if (new_registry_name and
               new_registry_name not in (registry.registry_name for registry in registries)):
            new_registry = Registry.get_by_name(new_registry_name)
            if new_registry:
                registries.append(new_registry)
        self.render_template('builder_account.html', params={'registries': registries})

class BuilderNewRegistryHandler(BaseHandler):
    @builder_login_required
    def post(self):
        key = ndb.Key(flat=self.user_info['user_id'])
        registry_name = self.request.get('registry_name')
        password = self.request.get('password')
        names = self.request.get('names')
        registry = Registry.create(registry_name, owner=key, insecure_password=password,
                                   names=names)
        return self.redirect_to('builder-account', new_registry=registry_name)

def parse_entries(entries):
    """Return a list of sections.

    Each returned section is a tuple (entry_name, section_entries), where
    section_entries are all of the entries in the section.

    entries:
        A list of entries (of type RegistryEntry), sorted in ascending order
        by section name.

    """
    if not entries:
        return []
    sectioned_entries = [(entries[0].section, [entries[0]])]
    for i in range(1, len(entries)):
        if entries[i].section != entries[i-1].section: # start a new section
            sectioned_entries.append((entries[i].section, []))
        sectioned_entries[-1][1].append(entries[i])
    return sectioned_entries
    
class BuildPage(BaseHandler):
    @get_registry_from_name
    def get(self, registry):
        if not self.user_info or registry.owner != ndb.Key(flat=self.user_info['user_id']):
            return self.redirect_to('builder-login',
                             next=self.uri_for('registry-build', registry_name=registry.registry_name))

        entries = RegistryEntry.query(ancestor=registry.key) \
                  .order(RegistryEntry.section, RegistryEntry.order) \
                  .fetch()
        sections = parse_entries(entries)
        self.render_template('registry_build.html', params={'registry': registry,
                                                            'sections': sections})

    @get_registry_from_name
    def post(self, registry):
        """Edit the registry based on the submitted info."""
        
        if not self.user_info or registry.owner != ndb.Key(flat=self.user_info['user_id']):
            return self.redirect_to('builder-login',
                             next=self.uri_for('registry-build', registry_name=registry.registry_name))

        request_type = self.request.get('request_type')
        if request_type == 'add_item':
            name = self.request.get('name')
            try:
                num_wanted = int(self.request.get('num_wanted'))
            except ValueError:
                num_wanted = 1
            section = self.request.get('section')
            high_entry = RegistryEntry.query(RegistryEntry.section==section, ancestor=registry.key) \
                                      .order(-RegistryEntry.order) \
                                      .get()
            if high_entry:
                high_order = high_entry.order
            else:
                high_order = 0.0
            entry = RegistryEntry(name=name, num_wanted=num_wanted, parent=registry.key,
                                  order=high_order+1, section=section)
            entry.put()
            logging.info(section)
            retval = {'num_wanted': num_wanted, 'name': name, 'section': section,
                      'id': entry.key.urlsafe()}
        elif request_type == 'delete_item':
            item_key = self.request.get('item_key')
            try:
                k = ndb.Key(urlsafe=item_key)
                k.delete()
            except TypeError:
                item_key = 0
            retval = {'item_key': item_key}
        else:
            webapp2.abort(405)

        if not self.request.get('ajax'): # was not an ajax query
            logging.info("Not AJAX query")
            return self.redirect_to('registry-build', registry_name=registry.registry_name)

        logging.info("Return JSON")
        self.response.content_type = 'application/json'
        self.response.write(json.encode(retval))

        


    def no_js_post(self, registry):
        """Adds a new entry to the registry without Javascript."""
        
    
class RegistryViewPage(BaseHandler):
    @get_registry_from_name
    def get(self, registry):
        viewer = self.registry_view_authorized(registry)
        if not viewer:
            return self.redirect_to('registry-verify',
                                    registry_name=registry.registry_name)
        entries = RegistryEntry.query(ancestor=registry.key).fetch()
        self.render_template("registry_view.html",
                             params={'registry': registry,
                                     'entries': entries,
                                     'viewer': None if viewer == 'anonymous_user' else viewer,
                                     'viewer_email': None if viewer == 'anonymous_user' else viewer.get().email})
            
    @get_registry_from_name
    def post(self, registry):
        viewer = self.registry_view_authorized(registry)
        if not viewer or viewer == 'anonymous_user':
            return self.redirect_to('registry-verify',
                                    registry_name=registry.registry_name)
        for id, num_claimed in self.request.POST.iteritems():
            try:
                parsed_id = int(id)
                parsed_num_claimed = int(num_claimed)
            except ValueError:
                continue
            entry = RegistryEntry.get_by_id(parsed_id, parent=registry.key)
            if entry and entry.num_claimed_by(viewer) != parsed_num_claimed:
                try:
                    claim = next(c for c in entry.claims if c.viewer == viewer)
                    claim.num = parsed_num_claimed
                except StopIteration:
                    entry.claims.append(Claim(viewer=viewer, num=parsed_num_claimed))
                entry.put()
        return self.redirect_to('registry-view', registry_name=registry.registry_name)
    
class RegistryVerifyPage(BaseHandler):
    @get_registry_from_name
    def get(self, registry):
        bad_password = self.request.get('bad_password')
        self.render_template("verify_registry.html", params={'registry': registry,
                                                             'bad_password': bad_password})

    @get_registry_from_name
    def post(self, registry):
        password = self.request.get('password')
        if self.authorize_registry_view(registry, password):
            return self.redirect_to('registry-view', registry_name=registry.registry_name)
        else:
            return self.redirect_to('registry-verify', registry_name=registry.registry_name,
                                    bad_password=True)

class RegistryLogoutPage(BaseHandler):
    @get_registry_from_name
    def get(self, registry):
        if self.session.get('cur_view') == registry.key.flat():
            self.unauthorize_registry_view()
        if self.user_info:
            if self.user_info.get('owner_tuple') is None:  # logged in as owner
                return self.redirect_to('builder-logout')
            if ndb.Key(flat=self.user_info.get('owner_tuple')) == registry.key:
                self.auth.unset_session()
        return self.redirect_to('home')

class RegistryLoginPage(BaseHandler):
    @get_registry_from_name
    def get(self, registry):
        self.render_template("registry_login.html", params={'registry': registry})

    @get_registry_from_name
    def post(self, registry):
        email = self.request.get('email')

        @ndb.transactional
        def get_or_create_user(email, parent_key):
            """Get or make a new viewer-type RegistryUser.

            Return a tuple. The first element is True if the user existed, False if it had to be made.
            The second is the user.

            """
            user = RegistryUser.get_by_id(email, parent=parent_key)
            if not user:
                user = RegistryUser.create(id=email, parent=parent_key)
                return (False, user)
            return (True, user)

        existed, user = get_or_create_user(email, registry.key)
        self.unauthorize_registry_view()
        self.auth.set_session(self.auth.store.user_to_dict(user), remember=True)
        return self.redirect_to('registry-view', registry_name=registry.registry_name)
    


config = {
  'webapp2_extras.auth': {
    'user_model': 'models.RegistryUser',
    'user_attributes': ['email', 'owner_tuple']
  },
  'webapp2_extras.sessions': {
    'secret_key': 'x874bdl'
  }
}

application = webapp2.WSGIApplication(
    [Route("/", MainPage, name='home'),
     Route("/login", BuilderLoginPage, name='builder-login'),
     Route("/logout", BuilderLogoutPage, name='builder-logout'),
     Route("/signup", BuilderSignupPage, name='builder-signup'),
     Route("/account", BuilderAccountPage, name='builder-account'),
     Route("/new_registry", BuilderNewRegistryHandler, name='builder-newregistry'),
     Route("/<registry_name>", RegistryViewPage, name='registry-view'),
     PathPrefixRoute("/<registry_name:[^/]+>", [
#         RedirectRoute("", redirect_to_name='registry-view'),
#         RedirectRoute("/", RegistryViewPage, strict_slash=True, name='registry-view'),
         RedirectRoute("/", redirect_to_name='registry-view'),
         Route("/verify", RegistryVerifyPage, name='registry-verify'),
         Route("/login", RegistryLoginPage, name='registry-login'),
         Route("/logout", RegistryLogoutPage, name='registry-logout'),
         Route("/build", BuildPage, name='registry-build')]),
     ],
    debug=True, config=config)

logging.getLogger().setLevel(logging.DEBUG)
