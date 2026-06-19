#!/bin/sh
set -eu

admin_email="${GLITCHTIP_ADMIN_EMAIL:-admin@example.com}"
admin_password="${GLITCHTIP_ADMIN_PASSWORD:-admin}"
organization_name="${GLITCHTIP_BOOTSTRAP_ORGANIZATION:-ITS}"
team_slug="${GLITCHTIP_BOOTSTRAP_TEAM:-platform}"
project_name="${GLITCHTIP_BOOTSTRAP_PROJECT:-its-platform}"
project_public_key="${GLITCHTIP_PROJECT_PUBLIC_KEY:-85dc29c1a9b645aaab8680880aea79db}"

echo "running GlitchTip database migrations"
./manage.py migrate --noinput

echo "ensuring GlitchTip admin user $admin_email"
GLITCHTIP_ADMIN_EMAIL="$admin_email" \
GLITCHTIP_ADMIN_PASSWORD="$admin_password" \
GLITCHTIP_BOOTSTRAP_ORGANIZATION="$organization_name" \
GLITCHTIP_BOOTSTRAP_TEAM="$team_slug" \
GLITCHTIP_BOOTSTRAP_PROJECT="$project_name" \
GLITCHTIP_PROJECT_PUBLIC_KEY="$project_public_key" \
./manage.py shell -c '
import os
import uuid
from django.contrib.auth import get_user_model
from django.apps import apps
from django.utils.text import slugify

email = os.environ["GLITCHTIP_ADMIN_EMAIL"]
password = os.environ["GLITCHTIP_ADMIN_PASSWORD"]
organization_name = os.environ["GLITCHTIP_BOOTSTRAP_ORGANIZATION"]
team_slug = slugify(os.environ["GLITCHTIP_BOOTSTRAP_TEAM"]) or "platform"
project_name = os.environ["GLITCHTIP_BOOTSTRAP_PROJECT"]
organization_slug = slugify(organization_name) or "its"
project_slug = slugify(project_name) or "its-platform"
project_public_key = uuid.UUID(os.environ["GLITCHTIP_PROJECT_PUBLIC_KEY"])

User = get_user_model()
user, created = User.objects.get_or_create(
    email=email,
    defaults={"is_staff": True, "is_superuser": True},
)
user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save(update_fields=["password", "is_staff", "is_superuser"])
action = "created" if created else "updated"
print(f"GlitchTip admin user {action}: {email}")

Organization = apps.get_model("organizations_ext", "Organization")
OrganizationUser = apps.get_model("organizations_ext", "OrganizationUser")
OrganizationOwner = apps.get_model("organizations_ext", "OrganizationOwner")
Team = apps.get_model("teams", "Team")
Project = apps.get_model("projects", "Project")
ProjectKey = apps.get_model("projects", "ProjectKey")

organization, org_created = Organization.objects.get_or_create(
    slug=organization_slug,
    defaults={"name": organization_name},
)
if organization.name != organization_name:
    organization.name = organization_name
    organization.save(update_fields=["name"])

organization_user, org_user_created = OrganizationUser.objects.get_or_create(
    organization=organization,
    user=user,
    defaults={"email": user.email, "role": 3},
)
updates = []
if organization_user.role != 3:
    organization_user.role = 3
    updates.append("role")
if organization_user.email != user.email:
    organization_user.email = user.email
    updates.append("email")
if updates:
    organization_user.save(update_fields=updates)

OrganizationOwner.objects.update_or_create(
    organization=organization,
    defaults={"organization_user": organization_user},
)

team, team_created = Team.objects.get_or_create(
    organization=organization,
    slug=team_slug,
)
team.members.add(organization_user)

project, project_created = Project.objects.get_or_create(
    organization=organization,
    slug=project_slug,
    defaults={"name": project_name, "platform": "python"},
)
project_updates = []
if project.name != project_name:
    project.name = project_name
    project_updates.append("name")
if not project.platform:
    project.platform = "python"
    project_updates.append("platform")
if project_updates:
    project.save(update_fields=project_updates)

team.projects.add(project)

project_key, key_created = ProjectKey.objects.get_or_create(
    project=project,
    name="Default",
    defaults={"public_key": project_public_key},
)
if project_key.public_key != project_public_key:
    project_key.public_key = project_public_key
    project_key.save(update_fields=["public_key"])

org_status = "created" if org_created else "ready"
org_user_status = "created" if org_user_created else "ready"
team_status = "created" if team_created else "ready"
project_status = "created" if project_created else "ready"
key_status = "created" if key_created else "ready"

print(f"GlitchTip organization {org_status}: {organization.slug}")
print(f"GlitchTip organization owner {org_user_status}: {email}")
print(f"GlitchTip team {team_status}: {team.slug}")
print(f"GlitchTip project {project_status}: {project.slug}")
print(f"GlitchTip project key {key_status}: {project_key.public_key}")
'

echo "GlitchTip bootstrap completed"
