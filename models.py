import time
import webapp2_extras.appengine.auth
import webapp2_extras.appengine.auth.models

from google.appengine.ext import ndb

from webapp2_extras import security

      

@ndb.transactional
def put_if_not_present(entity):
    """Stores the entity in datastore if it's not already there.
    
    Return False if the information is already in the datastore and True if it's not
    and then it's put there. This method is run as a transaction.

    """
    if not entity._key.get():
        entity.put()
        return True
    else:
        return False


class User(ndb.Model):
    """Stores user authentication credentials or authorization ids. This class doesn't store
    much other information besides this, as it's designed to be subclassed.

    An auth_id is a tuple/list of strings and ints, giving a key in flat notation. The final
    id should be an identifier for the user (an email address, for example). The parent should
    give the key of an owning entity for the user.
    The idea is that there are high-up users (who have a registry, say) and sub-users (who use a specific
    registry). 

    auth_ids are passed around by the auth module. The user shouldn't need to worry about them.
    This is somewhat more awkward than is ideal because of the way that webapp2_extras.auth works.
    Just see User.create for what you'll probably need to know.

    """

    # Hashed password. Can be omitted, in which case you can log in with a blank password.
    password = ndb.model.StringProperty()     


    #: The model used to store tokens.
    token_model = webapp2_extras.appengine.auth.models.UserToken

    def get_id(self):
        """Returns this user's unique auth_id."""
        return self._key.flat()
    

#    @classmethod
#    def get_by_auth_id(cls, auth_id):
#        """Return a user object based on an auth_id."""
#        return ndb.Key(flat=auth_id).get()

    @classmethod
    def get_by_auth_token(cls, auth_id, token):
        """Get a user object based on an auth_id and token.

        Return a tuple ``(User, timestamp)``, with a user object and
        the token timestamp, or ``(None, None)`` if both were not found.

        """
        token_key = cls.token_model.get_key(auth_id, 'auth', token)
        user_key = ndb.Key(flat=auth_id)
        valid_token, user = ndb.model.get_multi([token_key, user_key])
        if valid_token and user:
            timestamp = int(time.mktime(valid_token.created.timetuple()))
            return user, timestamp

        return None, None

    @classmethod
    def get_by_auth_password(cls, auth_id, password):
        """Return a user object, validating password.

        If the user exists and has no password, then it will match only an empty password.

        Raise webapp2_extras.auth.InvalidAuthIdError or webapp2_extras.auth.InvalidPasswordError if
        the username or password is wrong.
        
        """
        user = ndb.Key(flat=auth_id).get()
        if not user:
            raise webapp2_extras.auth.InvalidAuthIdError()

        # no password check if both password and user.password are unspecified
        if user.password and password:
            if not security.check_password_hash(password, user.password):
                raise webapp2_extras.auth.InvalidPasswordError()
        elif user.password or password:
            raise webapp2_extras.auth.InvalidPasswordError()

        return user


    @classmethod
    def create_auth_token(cls, auth_id):
        """Create a new authorization token for a given auth_id.

        Return a string with the authorization token.
        
        """
        return cls.token_model.create(auth_id, 'auth').token

    @classmethod
    def delete_auth_token(cls, auth_id, token):
        """Deletes a given authorization token."""
        cls.token_model.get_key(auth_id, 'auth', token).delete()

    @classmethod
    def create_signup_token(cls, auth_id):
        entity = cls.token_model.create(auth_id, 'signup')
        return entity.token

    @classmethod
    def delete_signup_token(cls, auth_id, token):
        cls.token_model.get_key(auth_id, 'signup', token).delete()

    @classmethod
    def create(cls, id=None, parent=None, key=None, **user_values):
        """Create a new user and add it to the datastore.

        The user can be given either by setting id and possibly parent, or by
        setting key, but not both. If id is set, then the new user gets a key
        based on id, a string or int, and parent, which should be an ndb.Key.
        If key is set, then it becomes the new key of the entity.
        
        Return the new user, or None if the user already exists. May throw an
        ndb.TransactionFailedError.

        """
        assert user_values.get('password') is None, \
               "Use password_raw instead of password to create new users."

        assert (id or key) and not (id and key), \
               "Give an id or a key, but not both."
        
        if 'password_raw' in user_values:
            user_values['password'] = security.generate_password_hash(
                user_values.pop('password_raw'), length=12)
            
        user = cls(id=id, parent=parent, key=key, **user_values)

        if put_if_not_present(user):
            return user
        return None

class RegistryUser(User):
    """A user of our registry app."""

    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @property
    def email(self):
        """The email address of the user."""
        return self._key.id()

    @property
    def owner_tuple(self):
        """The key of the parent of the user.

        If the user is a registry maker, this will be None.
        If the user is a registry viewer, this will be be the key of the registry
            that the user is looking at."""
        if self._key.parent():
            return self._key.parent().flat()
        return None

        
    

class Registry(ndb.Model):
    """A registry."""
    
    # A password for viewers to use to see the registry. Stored in plaintext.
    insecure_password = ndb.StringProperty(indexed=False)
    names = ndb.model.StringProperty()
    owner = ndb.model.KeyProperty(required=True)

    @property
    def registry_name(self):
        return self._key.id()

    
    @classmethod
    def get_by_name(cls, registry_name):
        """Return the registry, or None if it doesn't exist."""

        return cls.get_by_id(registry_name)

    @classmethod
    def create(cls, registry_name, **user_values):
        """Add a new Registry entity to datastore.

        registry_name:
            A unique name that will become the address of the registry.
            (Should decide which characters are allowed.)

        owner:
            The key of the RegistryUser who this registry belongs to.

        Return the newly added Registry entity. If add is unsuccessful, return None.
        (Might want to revise to raise an exception instead.)

        """
        assert 'parent' not in user_values
        entity = cls(id=registry_name, **user_values)
        if put_if_not_present(entity):
            return entity
        return None
        

        
class Claim(ndb.Model):
    """Represents a promise by a viewer to buy a certain number of an item."""

    viewer = ndb.KeyProperty(kind=RegistryUser)
    num = ndb.IntegerProperty(default=1)
    

class RegistryEntry(ndb.Model):
    """An item in a registry.

    The parent of the entity is the Registry that it belongs to."""

    # item name; for example, "napkins"
    name = ndb.StringProperty(required=True)

    # an optional section name; for example, "Cutlery"
    section = ndb.StringProperty(required=True, default="")

    # Items in each section are sorted according to order. It's float so that you can
    # easily insert an item between other items without needing to adjust their order.
    order = ndb.FloatProperty(required=True, default=0.0)
    
    num_wanted = ndb.IntegerProperty(default=1)
    claims = ndb.StructuredProperty(Claim, repeated=True)

    @property
    def remaining(self):
        return self.num_wanted - sum(claim.num for claim in self.claims)

    @property
    def claimed(self):
        return sum(claim.num for claim in self.claims)

    def num_claimed_by(self, viewer):
        return sum(claim.num for claim in self.claims if claim.viewer == viewer)
