from app.extensions import db


class BaseRepository:
    """
    Generic repository pattern base — keeps raw SQLAlchemy query construction
    out of the service layer so services stay focused on business logic.
    """
    model = None

    def get_by_id(self, id_):
        return self.model.query.get(id_)

    def list_all(self):
        return self.model.query

    def add(self, instance):
        db.session.add(instance)
        db.session.commit()
        return instance

    def update(self, instance, **kwargs):
        for key, value in kwargs.items():
            setattr(instance, key, value)
        db.session.commit()
        return instance

    def delete(self, instance):
        db.session.delete(instance)
        db.session.commit()

    @staticmethod
    def paginate(query, page: int, per_page: int):
        return query.paginate(page=page, per_page=per_page, error_out=False)
