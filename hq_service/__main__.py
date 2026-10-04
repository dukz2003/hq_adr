import os
import uvicorn

if __name__ == '__main__':
    # One worker owns one signer/cache/identity and the global request throttle.
    uvicorn.run('hq_service.app:app', host='0.0.0.0',
                port=int(os.getenv('PORT', '8080')), workers=1,
                access_log=False, proxy_headers=False)
