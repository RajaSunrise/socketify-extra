LIBRARY_NAME := libsocketify
UWS_LIBRARY_NAME := libuwebsockets
CC ?= clang
CXX ?= clang++

ARCH := amd64
ifeq ($(PLATFORM), arm64)
	ARCH := arm64
endif
ifeq ($(PLATFORM), aarch64)
	ARCH := arm64
endif
ifeq ($(PLATFORM), arm)
	ARCH := arm64
endif

clean:
	cd ../uWebSockets/uSockets && rm -f *.o *.a *.so *.obj *.lib *.dll
	cd ../uWebSockets/ && rm -f *.o *.a *.so *.obj *.lib *.dll
	rm -f *.o *.a *.so *.dll *.obj *.lib
	rm -rf ../uWebSockets/uSockets/boringssl/amd64
	rm -rf ../uWebSockets/uSockets/boringssl/vcpkg
	rm -rf ../uWebSockets/uSockets/boringssl/arm64

linux:
	$(MAKE) clean

	# build boringssl
	cd ../uWebSockets/uSockets/boringssl && mkdir -p $(ARCH) && cd $(ARCH) && cmake -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_BUILD_TYPE=Release .. && make crypto ssl

	# build uWebSockets
	cd ../uWebSockets/uSockets && $(CC) -I src -I boringssl/include -DUWS_WITH_PROXY -DLIBUS_USE_OPENSSL -DLIBUS_USE_LIBUV -pthread -fPIC -std=c11 -O3 -c src/*.c src/eventing/*.c src/crypto/*.c
	cd ../uWebSockets/uSockets && $(CXX) -I boringssl/include -DUWS_WITH_PROXY -DLIBUS_USE_OPENSSL -DLIBUS_USE_LIBUV -pthread -fPIC -std=c++17 -O3 -c src/crypto/*.cpp
	cd ../uWebSockets/uSockets && $(AR) rvs uSockets_linux_$(ARCH).a *.o

	# build CAPI + libsocketify
	$(CXX) -I ./src -I ../uWebSockets/src -I ../uWebSockets/uSockets/src -I ../uWebSockets/capi -I ../uWebSockets/uSockets/boringssl/include -DUWS_WITH_PROXY -pthread -fPIC -std=c++17 -c -O3 ./src/$(LIBRARY_NAME).cpp
	$(CXX) -shared -static-libstdc++ -static-libgcc -s -o ../$(LIBRARY_NAME)_linux_$(ARCH).so  $(LIBRARY_NAME).o ../uWebSockets/uSockets/uSockets_linux_$(ARCH).a ../uWebSockets/uSockets/boringssl/$(ARCH)/ssl/libssl.a ../uWebSockets/uSockets/boringssl/$(ARCH)/crypto/libcrypto.a -flto  -fPIC -lz -luv

linux-arm64:
	$(MAKE) clean

	# build boringssl for arm64
	cd ../uWebSockets/uSockets/boringssl && mkdir -p arm64 && cd arm64 && cmake -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_BUILD_TYPE=Release .. && make crypto ssl

	# build uWebSockets for arm64
	cd ../uWebSockets/uSockets && $(CC) -I src -I boringssl/include -DUWS_WITH_PROXY -DLIBUS_USE_OPENSSL -DLIBUS_USE_LIBUV -pthread -fPIC -std=c11 -O3 -c src/*.c src/eventing/*.c src/crypto/*.c
	cd ../uWebSockets/uSockets && $(CXX) -I boringssl/include -DUWS_WITH_PROXY -DLIBUS_USE_OPENSSL -DLIBUS_USE_LIBUV -pthread -fPIC -std=c++17 -O3 -c src/crypto/*.cpp
	cd ../uWebSockets/uSockets && $(AR) rvs uSockets_linux_arm64.a *.o

	# build CAPI + libsocketify for arm64
	$(CXX) -I ./src -I ../uWebSockets/src -I ../uWebSockets/uSockets/src -I ../uWebSockets/capi -I ../uWebSockets/uSockets/boringssl/include -DUWS_WITH_PROXY -pthread -fPIC -std=c++17 -c -O3 ./src/$(LIBRARY_NAME).cpp
	$(CXX) -shared -static-libstdc++ -static-libgcc -s -o ../$(LIBRARY_NAME)_linux_arm64.so  $(LIBRARY_NAME).o ../uWebSockets/uSockets/uSockets_linux_arm64.a ../uWebSockets/uSockets/boringssl/arm64/ssl/libssl.a ../uWebSockets/uSockets/boringssl/arm64/crypto/libcrypto.a -flto  -fPIC -lz -luv
