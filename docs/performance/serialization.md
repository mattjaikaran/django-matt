# Fast Serialization

High-performance JSON and MessagePack serialization.

## Fast JSON

```python
from django_matt import FastJsonResponse

@api.get("/data")
async def get_data(request):
    return FastJsonResponse({"items": large_list})
```

Uses orjson (fastest) or ujson as fallback.

## MessagePack

```python
from django_matt import MessagePackResponse

@api.get("/binary-data")
async def get_binary_data(request):
    return MessagePackResponse({"data": binary_data})
```

## Streaming

```python
from django_matt import StreamingJsonResponse, stream_json_list

@api.get("/large-list")
async def get_large_list(request):
    items = Product.objects.all().iterator()
    return StreamingJsonResponse(stream_json_list(items))
```
