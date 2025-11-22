import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { TacacsUserPublic } from "@/client"
import DeleteTacacsUser from "../TacacsUsers/DeleteTacacsUser"
import EditTacacsUser from "../TacacsUsers/EditTacacsUser"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface TacacsUserActionsMenuProps {
  tacacs_user: TacacsUserPublic
}

export const TacacsUserActionsMenu = ({ tacacs_user }: TacacsUserActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditTacacsUser tacacs_user={tacacs_user} />
        <DeleteTacacsUser tacacs_user={tacacs_user} />
      </MenuContent>
    </MenuRoot>
  )
}
