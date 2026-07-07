import os
import json
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import UploadedFile
from .serializers import UploadedFileSerializer
from .utils import parse_file_metadata, get_column_values


class FileUploadView(APIView):
    """View to handle file uploads."""

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist("file")
        if not files:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        for file_obj in files:
            if file_obj.size > settings.MAX_UPLOAD_SIZE:
                return Response(
                    {"error": f"File '{file_obj.name}' melebihi batas maksimal 50MB."},
                    status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )

        results = []
        for file_obj in files:
            uploaded_file = UploadedFile.objects.create(
                user=request.user,
                original_filename=file_obj.name,
                file_path=file_obj,
                file_size=file_obj.size,
                status="PROCESSING",
            )

            # 2. Parse metadata
            file_absolute_path = uploaded_file.file_path.path
            metadata = parse_file_metadata(file_absolute_path)

            if metadata["success"]:
                uploaded_file.delimiter = metadata["delimiter"]
                uploaded_file.encoding = metadata["encoding"]
                uploaded_file.row_count = metadata["row_count"]
                uploaded_file.column_count = metadata["column_count"]
                uploaded_file.status = "READY"
                uploaded_file.save()

                results.append(
                    {
                        "id": uploaded_file.id,
                        "filename": uploaded_file.original_filename,
                        "metadata": metadata,
                    }
                )
            else:
                uploaded_file.status = "ERROR"
                uploaded_file.save()
                results.append(
                    {
                        "id": uploaded_file.id,
                        "filename": uploaded_file.original_filename,
                        "error": metadata["error"],
                    }
                )

        return Response({"files": results}, status=status.HTTP_201_CREATED)


class PreviewFileView(APIView):
    def get(self, request, file_id, *args, **kwargs):
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id, user=request.user)
        except UploadedFile.DoesNotExist:
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )

        page = max(1, int(request.query_params.get("page", 1)))
        page_size = min(1000, max(1, int(request.query_params.get("page_size", 20))))
        sort_by = request.query_params.get("sort_by", None)
        sort_order = request.query_params.get("sort_order", "asc")
        filter_col = request.query_params.get("filter_col", None)
        filter_query = request.query_params.get("filter_query", None)
        filter_op = request.query_params.get("filter_op", "contains")
        filter_col2 = request.query_params.get("filter_col2", None)
        filter_op2 = request.query_params.get("filter_op2", "contains")
        filter_query2 = request.query_params.get("filter_query2", None)
        filter_logic = request.query_params.get("filter_logic", "AND")
        filters_raw = request.query_params.get("filters", None)
        filters = json.loads(filters_raw) if filters_raw else None

        file_absolute_path = uploaded_file.file_path.path
        metadata = parse_file_metadata(
            file_absolute_path,
            delimiter=uploaded_file.delimiter,
            encoding=uploaded_file.encoding,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filter_col=filter_col,
            filter_query=filter_query,
            filter_op=filter_op,
            filter_col2=filter_col2,
            filter_op2=filter_op2,
            filter_query2=filter_query2,
            filter_logic=filter_logic,
            filters=filters,
        )

        if metadata["success"]:
            return Response(metadata, status=status.HTTP_200_OK)
        return Response(
            {"error": metadata["error"]}, status=status.HTTP_400_BAD_REQUEST
        )


class FileDeleteView(APIView):
    def delete(self, request, file_id, *args, **kwargs):
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id, user=request.user)
            uploaded_file.delete()
            return Response({"success": True}, status=status.HTTP_200_OK)
        except UploadedFile.DoesNotExist:
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )


class ColumnValuesView(APIView):
    def get(self, request, file_id, *args, **kwargs):
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id, user=request.user)
        except UploadedFile.DoesNotExist:
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )
        column = request.query_params.get("column", None)
        if not column:
            return Response(
                {"error": "column parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            values = get_column_values(
                uploaded_file.file_path.path,
                column,
                delimiter=uploaded_file.delimiter,
                encoding=uploaded_file.encoding,
            )
            return Response({"values": values}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
