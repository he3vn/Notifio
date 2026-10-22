import flet as ft

def main(page: ft.Page):
    page.title = "Notifio"

    title = ft.TextField(label="Title")
    result = ft.Text("")                      # create it BEFORE save uses it

    def save(e):                              # only one save function
        result.value = title.value            # change the text
        title.value = ""                      # clear the box
        page.update()                         # redraw the screen

    page.add(ft.Text("Hi", size=20, color="blue"))
    page.add(title)
    page.add(ft.Button("Save", on_click=save))
    page.add(result)                          # now it appears right under Save

    bell = ft.Icon(ft.Icons.NOTIFICATION_ADD)
    label = ft.Text("New notification")
    btn = ft.Button("Save too", on_click=save)

    page.add(ft.Row([bell, label, btn]))
    page.add(ft.Container(content=ft.Text("Meeting at 5pm"), padding=10, bgcolor="grey", border_radius=8))
    page.add(ft.ListView(controls=[ft.Text(f"Notification {i}") for i in range(1, 31)], expand=True))

ft.run(main)