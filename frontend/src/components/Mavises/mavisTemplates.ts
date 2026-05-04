export interface MavisTemplateEntry {
  mavis_key: string
  mavis_value: string
  description: string
}

export interface MavisTemplate {
  id: string
  label: string
  description: string
  entries: MavisTemplateEntry[]
}

export const MAVIS_TEMPLATES: MavisTemplate[] = [
  {
    id: "active_directory",
    label: "Active Directory",
    description:
      "Microsoft Active Directory. Uses sAMAccountName for user lookup and AD password change scheme.",
    entries: [
      {
        mavis_key: "LDAP_HOSTS",
        mavis_value: "ldap://dc.example.com",
        description: "LDAP server URI. Use ldaps:// for TLS.",
      },
      {
        mavis_key: "LDAP_BASE",
        mavis_value: "DC=example,DC=com",
        description: "Base DN for user search.",
      },
      {
        mavis_key: "LDAP_SCOPE",
        mavis_value: "sub",
        description: "Search scope: sub (subtree), one, or base.",
      },
      {
        mavis_key: "LDAP_FILTER",
        mavis_value: "(&(objectClass=user)(sAMAccountName=%s))",
        description: "%s is replaced with the authenticating username.",
      },
      {
        mavis_key: "LDAP_BINDDN",
        mavis_value: "CN=svc-tacacs,CN=Users,DC=example,DC=com",
        description: "DN of service account used to bind to LDAP.",
      },
      {
        mavis_key: "LDAP_BINDPW",
        mavis_value: "changeme",
        description: "Password for the bind DN service account.",
      },
      {
        mavis_key: "LDAP_SERVER_TYPE",
        mavis_value: "AD",
        description: "Backend type. Use AD for Active Directory.",
      },
      {
        mavis_key: "LDAP_CHPASS_SCHEME",
        mavis_value: "ad",
        description: "Password change scheme. Required for AD.",
      },
      {
        mavis_key: "LDAP_USER_NAME_ATTR",
        mavis_value: "sAMAccountName",
        description: "LDAP attribute containing the login username.",
      },
    ],
  },
  {
    id: "openldap",
    label: "OpenLDAP",
    description:
      "Standard OpenLDAP / RFC 2307 directory. Uses posixAccount objectClass and uid attribute.",
    entries: [
      {
        mavis_key: "LDAP_HOSTS",
        mavis_value: "ldap://ldap.example.com",
        description: "LDAP server URI. Use ldaps:// for TLS.",
      },
      {
        mavis_key: "LDAP_BASE",
        mavis_value: "ou=people,dc=example,dc=com",
        description: "Base DN for user search.",
      },
      {
        mavis_key: "LDAP_SCOPE",
        mavis_value: "sub",
        description: "Search scope: sub (subtree), one, or base.",
      },
      {
        mavis_key: "LDAP_FILTER",
        mavis_value: "(&(objectClass=posixAccount)(uid=%s))",
        description: "%s is replaced with the authenticating username.",
      },
      {
        mavis_key: "LDAP_BINDDN",
        mavis_value: "cn=admin,dc=example,dc=com",
        description: "DN of service account used to bind to LDAP.",
      },
      {
        mavis_key: "LDAP_BINDPW",
        mavis_value: "changeme",
        description: "Password for the bind DN service account.",
      },
      {
        mavis_key: "LDAP_SERVER_TYPE",
        mavis_value: "openldap",
        description: "Backend type. Use openldap for standard LDAP.",
      },
      {
        mavis_key: "LDAP_USER_NAME_ATTR",
        mavis_value: "uid",
        description: "LDAP attribute containing the login username.",
      },
    ],
  },
  {
    id: "freeipa",
    label: "FreeIPA",
    description:
      "Red Hat FreeIPA / Identity Management. Uses IPA-specific DN structure under cn=accounts.",
    entries: [
      {
        mavis_key: "LDAP_HOSTS",
        mavis_value: "ldap://ipa.example.com",
        description: "LDAP server URI. Use ldaps:// for TLS.",
      },
      {
        mavis_key: "LDAP_BASE",
        mavis_value: "cn=accounts,dc=example,dc=com",
        description: "Base DN for IPA user search.",
      },
      {
        mavis_key: "LDAP_SCOPE",
        mavis_value: "sub",
        description: "Search scope: sub (subtree), one, or base.",
      },
      {
        mavis_key: "LDAP_FILTER",
        mavis_value: "(&(objectClass=person)(uid=%s))",
        description: "%s is replaced with the authenticating username.",
      },
      {
        mavis_key: "LDAP_BINDDN",
        mavis_value: "uid=svc-tacacs,cn=users,cn=accounts,dc=example,dc=com",
        description: "DN of service account used to bind to LDAP.",
      },
      {
        mavis_key: "LDAP_BINDPW",
        mavis_value: "changeme",
        description: "Password for the bind DN service account.",
      },
      {
        mavis_key: "LDAP_SERVER_TYPE",
        mavis_value: "openldap",
        description: "FreeIPA uses openldap as the server type.",
      },
      {
        mavis_key: "LDAP_USER_NAME_ATTR",
        mavis_value: "uid",
        description: "LDAP attribute containing the login username.",
      },
    ],
  },
]
