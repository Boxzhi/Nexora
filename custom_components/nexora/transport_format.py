"""Final, channel-specific formatting for local read-only query speech.

CN IM Hub uses the wechat:<account>:<sender> conversation id.  This is a
presentation hint only; it never changes query authority or permissions.
"""
import re

def format_query_text(cid,text):
    if not isinstance(cid,str) or not cid.startswith("wechat:") or not isinstance(text,str):
        return text
    text=text.replace("\r\n","\n").replace("\r","\n")
    return re.sub(r"(?<!\n)\n(?!\n)","\u2028",text)

def format_query_response(cid,response):
    data=response.as_dict()
    if data.get("response_type")!="action_done":
        return response
    speech=data.get("speech")
    if not isinstance(speech,dict) or set(speech)!={"plain"}:
        return response
    plain=speech["plain"]
    if not isinstance(plain,dict) or not set(plain)<={"speech","extra_data"}:
        return response
    raw=plain.get("speech")
    value=format_query_text(cid,raw)
    if value!=raw:
        if "extra_data" in plain:
            response.async_set_speech(value,extra_data=plain["extra_data"])
        else:
            response.async_set_speech(value)
    return response
