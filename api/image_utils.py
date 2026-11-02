"""
[추가 개발] ECR-002 "이미지 파일을 저장하고 사용자에게 제공하는 기능을 제작하기 때문에
사진과 같은 미디어 데이터들에 대한 용량 압축 기술이 필요함." / SFR-004 "멀티모달 기능의
과도한 사용 방지를 위해 이미지 압축 기술의 사용이 필요함."

기존 저장소에는 이미지 압축/저장 로직이 전혀 없었고(외부 URL만 참조), 실제로 이미지 파일을
업로드/저장하는 경로가 없었습니다. 이 모듈은 업로드된 이미지를 리사이즈 + 재인코딩하여
용량을 줄인 뒤 Django ImageField에 저장할 수 있는 형태로 돌려줍니다.
"""
import io

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image


def compress_image(uploaded_file, max_dimension=1600, quality=80):
    """
    업로드된 이미지 파일을 다음 규칙으로 압축합니다.
    - 가로/세로 중 긴 변이 max_dimension(px)을 넘으면 비율을 유지한 채 축소
    - JPEG로 재인코딩(quality 지정), RGBA/팔레트 이미지는 흰 배경 위에 합성 후 변환

    반환값은 InMemoryUploadedFile로, PlaceImage.image 필드에 그대로 저장할 수 있습니다.
    """
    image = Image.open(uploaded_file)

    # 투명도가 있는 이미지(PNG 등)는 흰 배경에 합성해야 JPEG 저장 시 검게 깨지지 않습니다.
    if image.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        rgba_image = image.convert('RGBA')
        background.paste(rgba_image, mask=rgba_image.split()[-1])
        image = background
    else:
        image = image.convert('RGB')

    width, height = image.size
    longest_side = max(width, height)
    if longest_side > max_dimension:
        scale = max_dimension / float(longest_side)
        image = image.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=quality, optimize=True)
    buffer.seek(0)

    original_name = getattr(uploaded_file, 'name', 'image')
    base_name = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
    new_name = f"{base_name}.jpg"

    return InMemoryUploadedFile(
        buffer, None, new_name, 'image/jpeg', buffer.getbuffer().nbytes, None
    )
