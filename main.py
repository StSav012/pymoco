if __name__ == "__main__":
    from standa import Standa, find_serials

    def main() -> None:
        s = Standa(0x130A)
        print(s.get_serial())
        print(s.get_version())
        print(s.__mode__)
        print(s.__parameters__)
        print(s.get_state())
        print(s.get_encoder_state())
        print(s.cur_pos)

        for ser in find_serials():
            print(hex(ser), Standa(ser).get_state().refined)

    main()
