# Staff accounts and Workforce

**Staff accounts** is the administrator-only login and authorization directory. Each account can
sign in to the municipal desk. Municipality administrators manage staff **inside their municipality
only** and cannot create `developer_operator` or other `administrator` accounts. The first
administrator for a new municipality is provisioned by a developer operator. Passwords are
write-only; account recovery continues through the staff forgot/reset-password flow.

**Workforce** is the operational directory for workers and teams assigned to tickets and work
orders. Workforce entries do not receive login credentials and cannot sign in. Creating a worker or
team therefore does not grant application access; create a Staff account separately when a person
needs authenticated access.
