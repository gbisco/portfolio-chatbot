def test_src_package_imports():
    import src
    import src.config
    import src.handler
    import src.auth
    import src.chat

    assert src.__name__ == "src"
    assert src.handler.__name__ == "src.handler"
    assert src.auth.__name__ == "src.auth"
    assert src.chat.__name__ == "src.chat"
