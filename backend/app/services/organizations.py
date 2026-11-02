from app.models.operations import Organization, OrganizationMembership


def organization_active(db, organization_id, user_id):
    if organization_id is None:
        return True
    org = db.get(Organization, organization_id)
    return bool(
        org
        and org.status == "verified"
        and db.query(OrganizationMembership)
        .filter_by(organization_id=organization_id, user_id=user_id, role="clinician", status="active")
        .first()
    )
