import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import UploadedFile
from .serializers import UploadedFileSerializer
from .utils import parse_file_metadata


class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {
                    "error": "Silakan Sign-in/Login terlebih dahulu untuk mengunggah file."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Allow multiple files to be uploaded at once
        files = request.FILES.getlist("file")
        if not files:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        results = []
        for file_obj in files:
            # 1. Save File object
            uploaded_file = UploadedFile.objects.create(
                user=request.user
                if request.user.is_authenticated
                else None,  # We should probably enforce login later
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
            uploaded_file = UploadedFile.objects.get(
                id=file_id, user=request.user if request.user.is_authenticated else None
            )
        except UploadedFile.DoesNotExist:
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        sort_by = request.query_params.get("sort_by", None)
        sort_order = request.query_params.get("sort_order", "asc")

        file_absolute_path = uploaded_file.file_path.path
        metadata = parse_file_metadata(
            file_absolute_path,
            delimiter=uploaded_file.delimiter,
            encoding=uploaded_file.encoding,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        if metadata["success"]:
            return Response(metadata, status=status.HTTP_200_OK)
        return Response(
            {"error": metadata["error"]}, status=status.HTTP_400_BAD_REQUEST
        )


class FileDeleteView(APIView):
    def delete(self, request, file_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            uploaded_file = UploadedFile.objects.get(id=file_id, user=request.user)
            uploaded_file.delete()
            return Response({"success": True}, status=status.HTTP_200_OK)
        except UploadedFile.DoesNotExist:
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )
