"""Shared pagination/filter/sort helpers used across list endpoints (NFR-04/05, FR-13)."""
from flask import request, current_app


def get_pagination_args():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", None, type=int)
    default = current_app.config["PAGINATION_DEFAULT_PAGE_SIZE"]
    max_size = current_app.config["PAGINATION_MAX_PAGE_SIZE"]
    per_page = min(per_page or default, max_size)
    return max(page, 1), max(per_page, 1)


def apply_sort(query, model, default_field="created_at", default_dir="desc"):
    sort_field = request.args.get("sort", default_field)
    sort_dir = request.args.get("dir", default_dir)
    column = getattr(model, sort_field, None)
    if column is None:
        column = getattr(model, default_field)
    return query.order_by(column.desc() if sort_dir == "desc" else column.asc())


def paginated_response(query, page, per_page, serializer):
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [serializer(item) for item in result.items],
        "page": result.page,
        "per_page": result.per_page,
        "total": result.total,
        "pages": result.pages,
    }
