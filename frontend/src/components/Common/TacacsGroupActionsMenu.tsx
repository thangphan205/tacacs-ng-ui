import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { TacacsGroupPublic } from "@/client"
import DeleteTacacsGroup from "../TacacsGroups/DeleteTacacsGroup"
import EditTacacsGroup from "../TacacsGroups/EditTacacsGroup"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface TacacsGroupActionsMenuProps {
  tacacs_group: TacacsGroupPublic
}

export const TacacsGroupActionsMenu = ({ tacacs_group }: TacacsGroupActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditTacacsGroup tacacs_group={tacacs_group} />
        <DeleteTacacsGroup tacacs_group={tacacs_group} />
      </MenuContent>
    </MenuRoot>
  )
}
