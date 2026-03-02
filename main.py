if __name__ == "__main__":
    from standa import Standa, find_serials

    def main() -> None:
        for ser in find_serials():
            s = Standa(ser)
            print(hex(ser), s.get_serial())
            print(s.get_version())
            print(s.__mode__)
            print(s.__parameters__)
            print(s.get_state())
            print(s.get_encoder_state())
            print("position", s.cur_pos, sep="=")

            s.move(s.cur_pos + 1000)
            print("position", s.cur_pos, sep="=")
            s.wait(1.0)
            s.move(s.cur_pos - 1000)
            s.wait()
            print("position", s.cur_pos, sep="=")

    main()
